"""Generate MCQ quiz questions from lecture content via LLM.

Primary: Groq Llama 3.3 70B. Fallback: Gemini 2.0 Flash.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re

from pipeline.model_prefs import gemini_model, openrouter_override
from pipeline.usage import record as _record_usage
from pipeline.usage import record_rate_limit as _record_rate_limit

logger = logging.getLogger(__name__)

# Canonical 10-question Bloom plan: the first 3 are low-order warm-ups (L1-L2),
# the majority are higher-order (apply / analyse / evaluate).
CHECKPOINT_BLOOM_PLAN: list[str] = [
    "remember",
    "understand", "understand",
    "apply", "apply", "apply",
    "analyse", "analyse",
    "evaluate", "evaluate",
]
_BLOOM_ORDER = {b: i for i, b in enumerate(["remember", "understand", "apply", "analyse", "evaluate"])}

# Prepended to every quiz-generation prompt so any math renders correctly in the
# KaTeX-enabled quiz UI (inline $...$, display $$...$$, single backslashes).
_MATH_RULE = (
    "MATH FORMATTING: write ALL mathematics as LaTeX — inline as $ ... $ and "
    "display as $$ ... $$. Use single backslashes (e.g. \\times, \\frac, x_1, \\gamma). "
    "Do NOT use \\( \\) or \\[ \\] delimiters, and do NOT double-escape backslashes. "
    "Subscripts like x_1 and operators like \\times must be inside $ ... $."
)


def validate_checkpoint_questions(questions: list[dict], target_count: int = 10) -> list[dict]:
    """Keep only structurally-valid questions and order them by Bloom level
    (easy -> hard). A question is NOT dropped merely for missing option
    explanations, so the final count stays at/near the target instead of
    silently shrinking to 5-6."""
    valid: list[dict] = []
    seen: set[str] = set()
    for q in questions:
        text = str(q.get("question_text", "")).strip()
        opts = q.get("options")
        correct = str(q.get("correct_answer", "")).strip()[:1].upper()
        if not text or text.casefold() in seen:
            continue
        if not isinstance(opts, list) or len(opts) != 4:
            continue
        if correct not in {"A", "B", "C", "D"}:
            continue
        valid.append(q)
        seen.add(text.casefold())
    valid.sort(key=lambda q: _BLOOM_ORDER.get(str(q.get("bloom_level", "understand")).lower(), 5))
    return valid[:target_count]

QUIZ_PROMPT = """You are a quiz designer for an educational lecture video. Based on this lecture content near timestamp {timestamp}:

{context}

Generate exactly {count} multiple-choice questions that FOLLOW BLOOM'S TAXONOMY, ordered from easiest to hardest.

Bloom distribution (keep this order):
  - The FIRST 3 are quick warm-ups: 1 "remember" (recall a key fact/term) + 2 "understand" (paraphrase/explain one core idea).
  - The MAJORITY of the rest make the learner actually think: about 3 "apply" (use the concept in a NEW situation or worked example) + 2 "analyse" (compare, contrast, break down components, identify cause/effect, spot which assumption breaks) + 2 "evaluate" (judge, critique, justify a choice between alternatives based on criteria).
  - Do NOT include any "create" level questions.

Each question must:
- Be self-contained (do not reference "the video", "the lecturer", or "the lecture")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Test the targeted cognitive level genuinely (an analyse-level Q must require analysis, not recall)
- Include `option_explanations`: an object with keys "A", "B", "C", "D". For the CORRECT option, one sentence on WHY it is right. For EACH wrong option, one sentence on WHY it is wrong AND name the specific misconception. Never just say "incorrect".

Return ONLY a JSON array of {count} objects in this exact shape:
[{{"question_text": "...",
   "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A",
   "explanation": "why the correct answer is correct",
   "option_explanations": {{"A": "why A is right/wrong", "B": "why B is right/wrong", "C": "why C is right/wrong", "D": "why D is right/wrong"}},
   "difficulty": "easy|medium|hard",
   "bloom_level": "remember|understand|apply|analyse|evaluate"}}]"""


def _select_context_chunks(chunks: list[dict], timestamp: float) -> list[dict]:
    """Pick chunks within ±60s of timestamp; if none, take 5 nearest."""
    in_window = [
        c for c in chunks
        if abs(float(c.get("start_time", 0.0)) - timestamp) <= 60.0
        or abs(float(c.get("end_time", 0.0)) - timestamp) <= 60.0
    ]
    if in_window:
        return in_window
    if not chunks:
        return []
    nearest = sorted(
        chunks,
        key=lambda c: abs(float(c.get("start_time", 0.0)) - timestamp),
    )
    return nearest[:5]


def _assemble_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        ts = float(c.get("start_time", 0.0))
        parts.append(f"[{ts:.0f}s] {c.get('text', '').strip()}")
    return "\n".join(parts)


def _parse_json_array(text: str) -> list[dict]:
    """Try direct json.loads, fallback to regex extraction. Tolerates truncation."""
    text = (text or "").strip()
    # Strip ```json fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # Truncation recovery: extract complete `{...}` objects one at a time
    objs: list[dict] = []
    depth = 0
    start = -1
    in_str = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                snippet = text[start : i + 1]
                try:
                    objs.append(json.loads(snippet))
                except json.JSONDecodeError:
                    pass
                start = -1
    if objs:
        logger.warning("Recovered %d questions from truncated/malformed JSON", len(objs))
        return objs
    raise ValueError(f"Could not parse JSON array from LLM response: {text[:200]}")


def _shuffle_options(q: dict) -> dict:
    """Randomize option order so the correct answer isn't always 'A'.

    LLMs strongly bias the correct answer to position A. We re-label the four
    options A-D in a random order and remap ``correct_answer`` +
    ``option_explanations`` to match. Mutates and returns ``q``.
    """
    opts = q.get("options") or []
    if len(opts) != 4:
        return q
    labels = ["A", "B", "C", "D"]
    parsed: list[tuple[str | None, str]] = []
    for i, o in enumerate(opts):
        m = re.match(r"^\s*([A-D])\s*[:.\-]\s*(.*)$", str(o), re.DOTALL)
        if m:
            parsed.append((m.group(1), m.group(2).strip()))
        else:
            parsed.append((labels[i], str(o).strip()))
    correct_letter = str(q.get("correct_answer", "A")).strip()[:1].upper()
    oe = q.get("option_explanations") if isinstance(q.get("option_explanations"), dict) else None

    order = list(range(4))
    random.shuffle(order)
    new_options: list[str] = []
    new_oe: dict[str, str] | None = {} if oe else None
    new_correct = "A"
    for new_idx, old_idx in enumerate(order):
        new_label = labels[new_idx]
        old_label, text = parsed[old_idx]
        new_options.append(f"{new_label}: {text}")
        if old_label == correct_letter:
            new_correct = new_label
        if new_oe is not None and old_label in oe:
            new_oe[new_label] = oe[old_label]
    q["options"] = new_options
    q["correct_answer"] = new_correct
    if new_oe is not None:
        q["option_explanations"] = new_oe
    return q


def _normalize_question(q: dict, shuffle: bool = True) -> dict:
    """Ensure required keys + safe defaults. Shuffles option order by default
    so the correct answer position is randomized."""
    bloom = str(q.get("bloom_level", "understand")).strip().lower() or "understand"
    if bloom not in {"remember", "understand", "apply", "analyse", "analyze", "evaluate"}:
        bloom = "understand"
    if bloom == "analyze":
        bloom = "analyse"
    out = {
        "question_text": str(q.get("question_text", "")).strip(),
        "options": list(q.get("options", [])),
        "correct_answer": str(q.get("correct_answer", "A")).strip()[:1].upper() or "A",
        "explanation": str(q.get("explanation", "")).strip(),
        "difficulty": str(q.get("difficulty", "medium")).strip().lower() or "medium",
        "bloom_level": bloom,
    }
    # Carry per-option explanations (why each option is right/wrong) so wrong
    # answers can be explained in the UI. Kept in sync through _shuffle_options.
    oe = q.get("option_explanations")
    if isinstance(oe, dict):
        cleaned = {
            k: str(v).strip()
            for k, v in oe.items()
            if k in ("A", "B", "C", "D") and str(v).strip()
        }
        out["option_explanations"] = cleaned or None
    else:
        out["option_explanations"] = None
    if shuffle:
        _shuffle_options(out)
    return out


def _call_groq(prompt: str, api_key: str, max_tokens: int = 12000) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def _call_gemini(prompt: str, api_key: str, max_tokens: int = 12000) -> str:
    from google import genai
    from google.genai import types
    import time as _time

    client = genai.Client(api_key=api_key)
    _record_usage("gemini", gemini_model("quizzes"))
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=gemini_model("quizzes"),
                contents=[types.Part.from_text(text=prompt)],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=max_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return response.text or ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc)
            if "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg.lower():
                _time.sleep(2 ** attempt)
                continue
            raise
    raise last_exc if last_exc else RuntimeError("Gemini call failed")


# ── Rate limiting (Gemini free tier = 5 requests/min) ──────────────────────
import time as _time  # noqa: E402

_LAST_LLM_CALL = 0.0
# ~5 req/min → 1 every 12s. Tunable via env; set 0 on paid tiers.
_MIN_LLM_INTERVAL = float(os.getenv("QUIZ_LLM_MIN_INTERVAL", "13"))


def _throttle() -> None:
    global _LAST_LLM_CALL
    dt = _time.time() - _LAST_LLM_CALL
    if dt < _MIN_LLM_INTERVAL:
        _time.sleep(_MIN_LLM_INTERVAL - dt)
    _LAST_LLM_CALL = _time.time()


def _call_llm_backoff(fn, prompt: str, key: str, max_tokens: int, retries: int = 4) -> str:
    """Call an LLM with proactive throttling + 429/rate-limit backoff-retry."""
    import re

    for attempt in range(retries):
        _throttle()
        try:
            return fn(prompt, key, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            s = str(exc)
            is_rate = "429" in s or "RESOURCE_EXHAUSTED" in s or "rate limit" in s.lower()
            if is_rate and "gemini" in getattr(fn, "__name__", ""):
                _record_rate_limit("gemini", s[:120])
            if is_rate and attempt < retries - 1:
                m = re.search(r"retry in ([0-9.]+)s", s)
                delay = min(65.0, (float(m.group(1)) + 2) if m else 20.0 * (attempt + 1))
                logger.warning("LLM rate-limited — waiting %.0fs (attempt %d/%d)", delay, attempt + 1, retries)
                _time.sleep(delay)
                continue
            raise
    return ""


def _call_openrouter(prompt: str, api_key: str, max_tokens: int = 8000,
                     model: str | None = None) -> str:
    """Text completion via OpenRouter. Tries FREE models first (0 credit cost),
    then the cheap paid model. Free models 429 often, so we fall through the
    list until one responds."""
    import json
    import urllib.error
    import urllib.request

    from pipeline.model_prefs import OR_FREE_TEXT_MODELS, OR_TEXT_PAID_FALLBACK

    # Explicit/user-chosen model wins; otherwise free list → paid fallback.
    explicit = model or openrouter_override("quizzes")
    candidates = [explicit] if explicit else [*OR_FREE_TEXT_MODELS, OR_TEXT_PAID_FALLBACK]

    for m in candidates:
        body = json.dumps({
            "model": m,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            r = json.load(urllib.request.urlopen(req, timeout=120))
            content = r["choices"][0]["message"]["content"] or ""
            if content.strip():
                return content
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 402, 503):  # rate-limited/no-credit → try next
                logger.info("OpenRouter %s unavailable (%s) — trying next", m, exc.code)
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            logger.info("OpenRouter %s failed (%s) — trying next", m, str(exc)[:60])
            continue
    return ""


# ── Vision helpers (lecture mode: quizzes grounded in on-screen frames) ─────

VISION_QUIZ_PREAMBLE = """\
You are ALSO given several KEYFRAMES captured from the screen around this point \
in the lecture (slides, diagrams, equations, code, charts, tables). Ground your \
questions in what is ACTUALLY VISIBLE in these frames \u2014 not only the transcript. \
When a diagram, graph, equation, table, or code snippet is shown, PREFER \
questions that require reading and reasoning about that on-screen content \
(e.g. "In the diagram, what happens to X when Y increases?"). Do not describe \
the frame itself or say "in the image"; make each question self-contained.

"""


def _read_image_bytes(path: str) -> bytes | None:
    """Read image bytes from a local file path OR a public URL; None on failure."""
    if not path:
        return None
    try:
        if path.startswith(("http://", "https://")):
            import urllib.request

            with urllib.request.urlopen(path, timeout=8) as resp:
                return resp.read()
        with open(path, "rb") as f:
            return f.read()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Keyframe read failed (%s): %s", path, str(exc)[:80])
        return None


def _select_keyframes(
    keyframes: list[dict], timestamp: float, window: float = 90.0, max_frames: int = 4
) -> list[str]:
    """Return up to ``max_frames`` keyframe file paths near ``timestamp``.

    Prefers frames within ``window`` seconds; if none, takes the nearest few.
    Samples evenly across the window so the frames are representative.
    """
    if not keyframes:
        return []
    near = [k for k in keyframes if abs(float(k.get("timestamp", 0)) - timestamp) <= window]
    if not near:
        near = sorted(keyframes, key=lambda k: abs(float(k.get("timestamp", 0)) - timestamp))[:max_frames]
    near = sorted(near, key=lambda k: float(k.get("timestamp", 0)))
    if len(near) > max_frames:
        step = len(near) / max_frames
        near = [near[int(i * step)] for i in range(max_frames)]
    return [str(k["file"]) for k in near if k.get("file")]


def _select_keyframes_span(
    keyframes: list[dict], start: float, end: float, max_frames: int = 8
) -> list[str]:
    """Return up to ``max_frames`` keyframe paths evenly spanning [start, end].

    Used for end_recall quizzes that synthesise a whole chapter, so the model
    sees representative frames from across the chapter (not just one point).
    """
    if not keyframes:
        return []
    inside = sorted(
        (k for k in keyframes if start <= float(k.get("timestamp", 0)) <= end),
        key=lambda k: float(k.get("timestamp", 0)),
    )
    if not inside:
        return []
    if len(inside) > max_frames:
        step = len(inside) / max_frames
        inside = [inside[int(i * step)] for i in range(max_frames)]
    return [str(k["file"]) for k in inside if k.get("file")]


def _call_gemini_vision(prompt: str, image_paths: list[str], api_key: str,
                        max_tokens: int = 8000) -> str:
    """Multimodal Gemini call: prompt + keyframe images."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts = [types.Part.from_text(text=prompt)]
    for p in image_paths:
        data = _read_image_bytes(p)
        if data:
            parts.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))
    _record_usage("gemini", gemini_model("quizzes"))
    response = client.models.generate_content(
        model=gemini_model("quizzes"),
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text or ""


def _call_openrouter_vision(prompt: str, image_paths: list[str], api_key: str,
                            max_tokens: int = 8000,
                            model: str | None = None) -> str:
    """Multimodal OpenRouter call. Tries FREE vision models first, then paid."""
    import base64
    import json
    import urllib.error
    import urllib.request

    from pipeline.model_prefs import OR_FREE_VISION_MODELS, OR_VISION_PAID_FALLBACK

    content: list[dict] = [{"type": "text", "text": prompt}]
    for p in image_paths:
        data = _read_image_bytes(p)
        if data:
            b64 = base64.b64encode(data).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    candidates = [model] if model else [*OR_FREE_VISION_MODELS, OR_VISION_PAID_FALLBACK]
    for m in candidates:
        body = json.dumps({
            "model": m,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": 0.5,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
            out = r["choices"][0]["message"]["content"] or ""
            if out.strip():
                return out
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 402, 503):
                logger.info("OpenRouter vision %s unavailable (%s) — trying next", m, exc.code)
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            logger.info("OpenRouter vision %s failed (%s) — trying next", m, str(exc)[:60])
            continue
    return ""


def _call_vision_backoff(fn, prompt: str, images: list[str], key: str,
                         max_tokens: int, retries: int = 4) -> str:
    """Like ``_call_llm_backoff`` but for multimodal (image-bearing) calls."""
    import re

    for attempt in range(retries):
        _throttle()
        try:
            return fn(prompt, images, key, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            s = str(exc)
            is_rate = "429" in s or "RESOURCE_EXHAUSTED" in s or "rate limit" in s.lower()
            if is_rate and attempt < retries - 1:
                m = re.search(r"retry in ([0-9.]+)s", s)
                delay = min(65.0, (float(m.group(1)) + 2) if m else 20.0 * (attempt + 1))
                logger.warning("Vision LLM rate-limited \u2014 waiting %.0fs (%d/%d)",
                               delay, attempt + 1, retries)
                _time.sleep(delay)
                continue
            raise
    return ""


def _generate_quiz_vision_one(
    video_id: str, timestamp: float, chunks: list[dict],
    image_paths: list[str], count_per_cp: int = 10,
) -> list[dict]:
    """Generate quizzes for a SINGLE checkpoint using transcript + on-screen
    keyframes (Gemini vision, OpenRouter vision fallback)."""
    selected = _select_context_chunks(chunks, timestamp)
    context = _assemble_context(selected) if selected else "[no transcript available]"
    prompt = VISION_QUIZ_PREAMBLE + QUIZ_PROMPT.format(
        timestamp=f"{timestamp:.0f}s", context=context, count=count_per_cp,
    )
    prompt = _MATH_RULE + "\n\n" + prompt
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    max_tokens = max(4000, 400 * count_per_cp)

    raw = ""
    if gemini_key:
        try:
            raw = _call_vision_backoff(_call_gemini_vision, prompt, image_paths, gemini_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini vision quiz at %.0fs failed: %s", timestamp, str(exc)[:120])
    if not raw and or_key:
        try:
            raw = _call_vision_backoff(_call_openrouter_vision, prompt, image_paths, or_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouter vision quiz at %.0fs failed: %s", timestamp, str(exc)[:120])
    if not raw:
        return []
    parsed = _parse_json_array(raw)
    return [_normalize_question(q) for q in parsed if q.get("question_text")]


def generate_quiz_questions(
    video_id: str,
    timestamp: float,
    chunks: list[dict],
    count: int = 10,
) -> list[dict]:
    """Generate MCQ questions from chunks near a timestamp.

    Default count of 10 per checkpoint produces a higher-order Bloom set:
    1 remember + 1 understand + 3 apply + 3 analyse + 2 evaluate.
    """
    selected = _select_context_chunks(chunks, timestamp)
    if not selected:
        logger.warning("No chunks available for quiz at %s@%ss", video_id, timestamp)
        return []

    context = _assemble_context(selected)
    prompt = _MATH_RULE + "\n\n" + QUIZ_PROMPT.format(timestamp=f"{timestamp:.0f}s", context=context, count=count)

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    last_err: Exception | None = None
    raw = ""
    if groq_key:
        try:
            raw = _call_groq(prompt, groq_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq quiz gen failed, falling back to Gemini: %s", exc)
            last_err = exc

    if not raw and gemini_key:
        try:
            raw = _call_gemini(prompt, gemini_key)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini quiz gen also failed: %s", exc)
            last_err = exc

    if not raw:
        raise RuntimeError(f"All LLM providers failed: {last_err}")

    parsed = _parse_json_array(raw)
    normalized = [_normalize_question(q) for q in parsed if q.get("question_text")]
    return validate_checkpoint_questions(normalized, target_count=count)


# ── Multi-checkpoint batched generation ──────────────────────────

MULTI_QUIZ_PROMPT = """You are a quiz designer for an educational lecture video.
You will generate quizzes for {n_checkpoints} different checkpoints from the same lecture, in a single response.

For EACH checkpoint, generate exactly {count_per_cp} multiple-choice questions, weighted toward higher-order thinking (Bloom's taxonomy):
  - a couple of quick warm-ups at "remember" (recall a key fact/term) and "understand" (paraphrase one core idea)
  - the MAJORITY at "apply" (use the concept in a NEW situation or worked example) and "analyse" (compare, contrast, break down components, identify cause/effect)
  - at least one at "evaluate" (judge, critique, justify a choice based on criteria)

Do NOT include any "create" level questions. Always include at least one apply, one analyse, and one evaluate question, and spend most effort on those.

Each question must:
- Be self-contained (do not reference "the video", "the lecturer", or "the lecture")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Test the targeted cognitive level genuinely
- Include `option_explanations`: an object with keys "A","B","C","D" — for the correct option say WHY it is right; for each wrong option say WHY it is wrong AND name the misconception.

Lecture content per checkpoint:
{checkpoints_block}

Return ONE FLAT JSON array containing ALL {total_questions} questions across all checkpoints. Each question MUST include a `checkpoint_timestamp` field with the exact timestamp number from the matching checkpoint header above:

[
  {{"checkpoint_timestamp": 30,
    "question_text": "...",
    "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
    "correct_answer": "A",
    "explanation": "...",
    "option_explanations": {{"A": "why A is right/wrong", "B": "why B is right/wrong", "C": "why C is right/wrong", "D": "why D is right/wrong"}},
    "difficulty": "medium",
    "bloom_level": "apply"}},
  ...{total_questions} total entries...
]

Return ONLY the JSON array, no other text."""


def generate_quizzes_for_checkpoints(  # noqa: keep signature stable
    video_id: str,
    checkpoint_timestamps: list[float],
    chunks: list[dict],
    count_per_cp: int = 10,
    batch_size: int | None = None,
    keyframes: list[dict] | None = None,
) -> dict[float, list[dict]]:
    """Generate quizzes for checkpoints, DYNAMICALLY BATCHED across several LLM
    calls so no single call blows past the model's output-token limit (which
    truncates the JSON and silently loses questions).

    If ``keyframes`` is provided (LECTURE mode), each checkpoint is generated
    individually with its nearby on-screen frames (Gemini vision \u2192 OpenRouter
    vision), so questions can be grounded in slides/diagrams/equations/code.
    Checkpoints with no nearby frame, or where vision yields nothing, fall back
    to the transcript-only text path. When ``keyframes`` is None/empty
    (PODCAST mode, or vision unavailable) the fast batched text path is used.

    Returns {timestamp: [questions]}. Batches are generated independently, so a
    failure in one batch never wipes the others.
    """
    if not checkpoint_timestamps:
        return {}

    # ── Vision path (lecture mode): per-checkpoint, transcript + frames ──
    if keyframes:
        out: dict[float, list[dict]] = {}
        for ts in checkpoint_timestamps:
            frames = _select_keyframes(keyframes, ts)
            qs: list[dict] = []
            if frames:
                try:
                    qs = _generate_quiz_vision_one(video_id, ts, chunks, frames, count_per_cp)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Vision quiz at %.0fs failed: %s", ts, str(exc)[:100])
            if not qs:
                # No frame nearby, or vision produced nothing → transcript fallback.
                qs = _generate_quiz_batch(video_id, [ts], chunks, count_per_cp).get(ts, [])
            out[ts] = qs
        return out

    # ── Text path (podcast mode / no keyframes): fast dynamic batching ──
    # Size each batch so its expected output stays well under the model's output
    # cap (~8k tokens). A question with explanations ≈ ~300 tokens.
    if batch_size is None:
        per_cp_tokens = max(1, count_per_cp * 300)
        batch_size = max(1, min(8, 6000 // per_cp_tokens))

    out = {}
    n = len(checkpoint_timestamps)
    for i in range(0, n, batch_size):
        batch = checkpoint_timestamps[i : i + batch_size]
        logger.info(
            "Quiz batch %d-%d of %d (%d checkpoints)",
            i + 1, min(i + batch_size, n), n, len(batch),
        )
        try:
            out.update(_generate_quiz_batch(video_id, batch, chunks, count_per_cp))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Quiz batch at %.0fs failed: %s", batch[0], exc)
            for ts in batch:
                out.setdefault(ts, [])
    return out


def _generate_quiz_batch(
    video_id: str,
    checkpoint_timestamps: list[float],
    chunks: list[dict],
    count_per_cp: int = 7,
) -> dict[float, list[dict]]:
    """Generate quizzes for a SMALL batch of checkpoints in one LLM call, with
    per-checkpoint fallback for any the batched call missed.
    """
    if not checkpoint_timestamps:
        return {}

    # Build per-checkpoint context blocks
    blocks: list[str] = []
    for i, ts in enumerate(checkpoint_timestamps, 1):
        selected = _select_context_chunks(chunks, ts)
        if not selected:
            blocks.append(f"--- Checkpoint {i} (timestamp={ts:.0f}s) ---\n[no transcript available]")
            continue
        ctx = _assemble_context(selected)
        blocks.append(f"--- Checkpoint {i} (timestamp={ts:.0f}s) ---\n{ctx}")

    prompt = MULTI_QUIZ_PROMPT.format(
        n_checkpoints=len(checkpoint_timestamps),
        count_per_cp=count_per_cp,
        total_questions=len(checkpoint_timestamps) * count_per_cp,
        checkpoints_block="\n\n".join(blocks),
    )

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    raw = ""
    # ~300 tokens per question with explanations + JSON overhead + buffer.
    max_tokens = max(8000, 400 * count_per_cp * len(checkpoint_timestamps))
    # Gemini first (default engine) with throttle + 429 backoff; Groq fallback.
    if gemini_key:
        try:
            raw = _call_llm_backoff(_call_gemini, prompt, gemini_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini multi-quiz failed: %s", str(exc)[:120])
    if not raw and groq_key:
        try:
            raw = _call_llm_backoff(_call_groq, prompt, groq_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq multi-quiz failed: %s", str(exc)[:120])
    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not raw and or_key:
        try:
            raw = _call_llm_backoff(_call_openrouter, prompt, or_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouter multi-quiz failed: %s", str(exc)[:120])

    out: dict[float, list[dict]] = {ts: [] for ts in checkpoint_timestamps}
    if raw:
        try:
            parsed = _parse_json_array(raw)
            for entry in parsed:
                if not isinstance(entry, dict) or not entry.get("question_text"):
                    continue
                ts_val = entry.get("checkpoint_timestamp")
                if not isinstance(ts_val, (int, float)):
                    continue
                best = min(checkpoint_timestamps, key=lambda t: abs(t - float(ts_val)))
                out[best].append(_normalize_question(entry))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse batched quiz response: %s", exc)

    # Only per-checkpoint fallback if the batch call actually returned data.
    # An empty response usually means a rate-limit window — don't hammer the
    # API; those checkpoints stay uncached and are generated on the next run.
    if raw:
        missing = [ts for ts in checkpoint_timestamps if not out.get(ts)]
        if missing:
            logger.info(
                "Batch returned %d/%d; per-checkpoint fallback for %d",
                len(checkpoint_timestamps) - len(missing), len(checkpoint_timestamps), len(missing),
            )
            for ts in missing:
                try:
                    out[ts] = generate_quiz_questions(video_id, ts, chunks, count=count_per_cp)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Fallback quiz gen at %.0fs failed: %s", ts, str(exc)[:80])
                    out[ts] = []

    return out


# ── Chapter-aware quiz generation (pretest / mid-recall / end-recall) ────────

CHAPTER_QUIZ_PROMPTS: dict[str, str] = {
    "pretest": """You are a quiz designer creating **pretest** questions for a chapter of an educational lecture.

The learner has NOT watched this content yet. The purpose is to PRIME their brain — spark curiosity and activate prior knowledge so they pay attention during the chapter.

Chapter title: {chapter_title}
Chapter content:
{context}

Generate exactly {count} multiple-choice questions following these rules:

NATURE — CURIOSITY-TRIGGERING & ACCESSIBLE:
- Frame questions as "What do you think…", "Which of these would…", "Before watching, predict…"
- The TOPIC of "{chapter_title}" may itself be advanced/technical — your job is to make it feel APPROACHABLE to a complete layman. Do NOT make the questions artificially hard. Lower the barrier, don't raise it.
- Lead with EVERYDAY, REAL-WORLD ANALOGIES so a non-expert can reason about the idea using common sense. If a technical term is unavoidable, gloss it in plain words INSIDE the question.
- Getting it wrong is expected and fine — that's the point.

DIFFICULTY: Easy to Medium. Keep the wording simple and the concepts intuitive; the analogy should do the heavy lifting.
BLOOM DISTRIBUTION:
  - {count_remember} at level "remember" (prior knowledge recall)
  - {count_understand} at level "understand" (intuitive reasoning)

Each question must:
- Be self-contained (no references to "the video" or "the lecturer")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Include `option_explanations` — an object with keys "A","B","C","D". For pretests these must be DETAILED and a bit LENGTHY (3-5 sentences each):
  - For the CORRECT option: teach the concept in full — explain WHY it's right, build intuition with a concrete real-world ANALOGY, and connect it to what the learner is about to watch.
  - For each WRONG option: explain WHY it's wrong, name the specific misconception, and gently correct it — again in plain, everyday language.
  - Do NOT be terse. This is a teaching moment; write like a patient tutor explaining to a curious beginner.

Return ONLY a JSON array:
[{{"question_text": "...",
   "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A",
   "explanation": "a detailed, plain-language reason the correct answer is correct, with an analogy",
   "option_explanations": {{"A": "Detailed 3-5 sentence explanation with an analogy...", "B": "Detailed why-wrong + misconception...", "C": "...", "D": "..."}},
   "difficulty": "easy|medium",
   "bloom_level": "remember|understand"}}]""",

    "mid_recall": """You are a quiz designer creating **mid-recall** questions for a specific section within a chapter.

The learner JUST watched this content 5-10 minutes ago. The purpose is to LOCK IN the specific concept they just learned — test whether it stuck.

Chapter title: {chapter_title}
Relevant section content:
{context}

Generate exactly {count} multiple-choice questions following these rules:

NATURE — SPECIFIC / "DID YOU GET IT?":
- Questions should test the exact concept just covered, not general knowledge
- Be specific: reference particular facts, formulas, examples from the content
- If the content showed a truth table, test that truth table
- If it defined a term, test that definition with a twist

DIFFICULTY: Medium
BLOOM DISTRIBUTION:
  - {count_understand} at level "understand" (explain / paraphrase the concept)
  - {count_apply} at level "apply" (use the concept in a new situation)

Each question must:
- Be self-contained (no references to "the video" or "the lecturer")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Include `option_explanations` — an object with keys "A","B","C","D"
  - For the CORRECT option: 1-2 sentences explaining why it's right
  - For each WRONG option: 1-2 sentences explaining why it's wrong AND naming the specific misconception
  - Do NOT just say "this is incorrect". Always explain WHY.

Return ONLY a JSON array:
[{{"question_text": "...",
   "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A",
   "explanation": "short reason the correct answer is correct",
   "option_explanations": {{"A": "Correct because...", "B": "Wrong because...", "C": "Wrong because...", "D": "Wrong because..."}},
   "difficulty": "medium",
   "bloom_level": "understand|apply"}}]""",

    "end_recall": """You are a quiz designer creating **end-of-chapter recall** questions.

The learner has finished this entire chapter. The purpose is to SYNTHESIZE — test whether they can combine multiple concepts from across the chapter, not just recall isolated facts.

Chapter title: {chapter_title}
Full chapter content:
{context}

Generate exactly {count} multiple-choice questions following these rules:

NATURE — SYNTHESIS / INTEGRATION:
- Questions should combine 2-3 concepts from the chapter
- "Given what you learned about X and Y, which statement is true about Z?"
- Compare and contrast different ideas from the chapter
- Apply concepts to novel situations not directly shown in the lecture

DIFFICULTY: Medium to Hard
BLOOM DISTRIBUTION:
  - {count_apply} at level "apply" (use concepts in a new context)
  - {count_analyse} at level "analyse" (compare, contrast, identify cause-effect)
  - {count_evaluate} at level "evaluate" (judge, critique, justify a choice)

Each question must:
- Be self-contained (no references to "the video" or "the lecturer")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Include `option_explanations` — an object with keys "A","B","C","D"
  - For the CORRECT option: 1-2 sentences explaining why it's right
  - For each WRONG option: 1-2 sentences explaining why it's wrong AND naming the specific misconception
  - Do NOT just say "this is incorrect". Always explain WHY.

Return ONLY a JSON array:
[{{"question_text": "...",
   "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A",
   "explanation": "short reason the correct answer is correct",
   "option_explanations": {{"A": "Correct because...", "B": "Wrong because...", "C": "Wrong because...", "D": "Wrong because..."}},
   "difficulty": "medium|hard",
   "bloom_level": "apply|analyse|evaluate"}}]""",
}


def _get_bloom_counts(quiz_type: str, count: int) -> dict[str, int]:
    """Return per-level counts for a given quiz type and total question count."""
    if quiz_type == "pretest":
        # Split evenly between remember and understand
        r = count // 2
        return {"count_remember": r, "count_understand": count - r}
    elif quiz_type == "mid_recall":
        u = count // 2
        return {"count_understand": u, "count_apply": count - u}
    else:  # end_recall
        a = max(1, count // 3)
        an = max(1, count // 3)
        e = count - a - an
        return {"count_apply": a, "count_analyse": an, "count_evaluate": e}


def _normalize_chapter_question(q: dict, quiz_type: str) -> dict:
    """Normalize a chapter quiz question, including option_explanations."""
    # Don't shuffle yet — option_explanations are keyed A-D on the ORIGINAL
    # order; we attach them first, then shuffle everything together.
    base = _normalize_question(q, shuffle=False)
    base["quiz_type"] = quiz_type

    # option_explanations
    oe = q.get("option_explanations")
    if isinstance(oe, dict):
        base["option_explanations"] = {
            k: str(v).strip() for k, v in oe.items() if k in ("A", "B", "C", "D") and v
        }
    else:
        base["option_explanations"] = None

    # misconception_tags — extract from distractor explanations if LLM included them
    tags = q.get("misconception_tags")
    if isinstance(tags, list):
        base["misconception_tags"] = [str(t).strip() for t in tags if t]
    else:
        base["misconception_tags"] = None

    # Now randomize option order (remaps correct_answer + option_explanations).
    _shuffle_options(base)
    # Derive legacy single explanation from the (post-shuffle) correct option.
    if isinstance(base.get("option_explanations"), dict):
        correct = base["correct_answer"]
        if correct in base["option_explanations"]:
            base["explanation"] = base["option_explanations"][correct]

    return base


def _get_chapter_chunks(
    chunks: list[dict], start_time: float, end_time: float,
) -> list[dict]:
    """Get chunks that fall within a chapter's time range."""
    return [
        c for c in chunks
        if float(c.get("start_time", 0)) >= start_time - 5
        and float(c.get("start_time", 0)) < end_time + 5
    ]


def _compute_mid_recall_count(chapter_minutes: float) -> int:
    """Determine how many mid-recall quiz blocks to place in a chapter."""
    if chapter_minutes < 6:
        return 0
    if chapter_minutes < 12:
        return 1
    if chapter_minutes < 20:
        return 2
    if chapter_minutes < 30:
        return 3
    return min(5, max(1, int(chapter_minutes // 8) - 1))


def _compute_chapter_count(duration_minutes: float) -> int:
    """Target chapter count from video duration, with a PROGRESSIVE chapter
    length that widens for longer videos.

    Baseline: a 2-hour video uses **12-minute** chapters; for every extra hour
    the chapter length grows by **3 minutes** (2 hr → 12 min, 3 hr → 15, 4 hr →
    18, 7 hr → 27 …). Videos under 2 hours use the 12-minute baseline.

    Bounded to 1..30 chapters so very long videos stay manageable.

    NOTE: this is the fallback for videos WITHOUT creator-provided (YouTube)
    chapters. When YouTube chapters exist, use those timestamps instead.
    """
    hours = duration_minutes / 60.0
    chapter_len = 12.0 + 3.0 * max(0.0, hours - 2.0)
    return max(1, min(30, round(duration_minutes / chapter_len)))


def generate_chapter_quizzes(
    video_id: str,
    chapter: dict,
    chunks: list[dict],
    quiz_type: str,
    count: int = 5,
    mid_recall_timestamp: float | None = None,
    keyframes: list[dict] | None = None,
) -> list[dict]:
    """Generate quiz questions for a single chapter + quiz_type.

    For mid_recall, pass the specific timestamp where the recall should fire;
    only nearby chunks will be used as context.

    Args:
        video_id: YouTube video ID.
        chapter: dict with keys: id, idx, start_time, end_time, title.
        chunks: All chunks for the video.
        quiz_type: One of "pretest", "mid_recall", "end_recall".
        count: Number of questions to generate (default 5).
        mid_recall_timestamp: For mid_recall only — the specific timestamp.

    Returns:
        List of normalized question dicts ready for DB insertion.
    """
    if quiz_type not in CHAPTER_QUIZ_PROMPTS:
        raise ValueError(f"Unknown quiz_type: {quiz_type}")

    start = float(chapter.get("start_time", 0))
    end = float(chapter.get("end_time", 0))
    title = chapter.get("title", f"Chapter {chapter.get('idx', '?')}")

    # Select context chunks
    if quiz_type == "mid_recall" and mid_recall_timestamp is not None:
        # Use chunks near the specific mid-recall point (±60s)
        selected = _select_context_chunks(chunks, mid_recall_timestamp)
    else:
        # Use all chunks in the chapter
        selected = _get_chapter_chunks(chunks, start, end)

    if not selected:
        logger.warning("No chunks for %s quiz at chapter '%s'", quiz_type, title)
        return []

    context = _assemble_context(selected)
    bloom_counts = _get_bloom_counts(quiz_type, count)

    base_prompt = CHAPTER_QUIZ_PROMPTS[quiz_type].format(
        chapter_title=title,
        context=context,
        count=count,
        **bloom_counts,
    )
    prompt = _MATH_RULE + "\n\n" + base_prompt

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    raw = ""
    max_tokens = max(8000, 1500 * count)

    # ── Vision path ────────────────────────────────────────────────
    # If keyframes exist for this chapter, ground the quiz in the on-screen
    # board/slide content. mid_recall → frames near the recall point;
    # end_recall → frames spanning the chapter; pretest → frames near the start
    # (the very first pretest usually has none yet → falls through to text).
    image_paths: list[str] = []
    if keyframes:
        if quiz_type == "mid_recall" and mid_recall_timestamp is not None:
            image_paths = _select_keyframes(keyframes, mid_recall_timestamp, window=90, max_frames=4)
        elif quiz_type == "end_recall":
            image_paths = _select_keyframes_span(keyframes, start, end, max_frames=8)
        else:  # pretest
            image_paths = _select_keyframes(keyframes, start, window=120, max_frames=4)
    if image_paths:
        vision_prompt = _MATH_RULE + "\n\n" + VISION_QUIZ_PREAMBLE + base_prompt
        if gemini_key:
            try:
                # retries=1: on a 429, fail fast to OpenRouter vision / the text
                # chain instead of waiting minutes on Gemini's free-tier backoff.
                raw = _call_vision_backoff(_call_gemini_vision, vision_prompt, image_paths, gemini_key, max_tokens, retries=1)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini vision chapter quiz failed: %s", str(exc)[:120])
        if not raw and or_key:
            try:
                raw = _call_vision_backoff(_call_openrouter_vision, vision_prompt, image_paths, or_key, max_tokens, retries=2)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenRouter vision chapter quiz failed: %s", str(exc)[:120])

    # ── Text path (fallback / when no keyframes) ───────────────────
    # Stable chain: Gemini (free) → Groq (free) → OpenRouter (paid), each with
    # proactive throttle + 429 backoff so chapter quizzes never cascade-fail.
    if not raw and gemini_key:
        try:
            # retries=1: fail fast to Groq (separate quota) if Gemini free tier is exhausted.
            raw = _call_llm_backoff(_call_gemini, prompt, gemini_key, max_tokens, retries=1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini chapter quiz failed: %s", str(exc)[:120])
    if not raw and groq_key:
        try:
            raw = _call_llm_backoff(_call_groq, prompt, groq_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq chapter quiz failed: %s", str(exc)[:120])
    if not raw and or_key:
        try:
            raw = _call_llm_backoff(_call_openrouter, prompt, or_key, max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouter chapter quiz failed: %s", str(exc)[:120])

    if not raw:
        return []

    parsed = _parse_json_array(raw)
    questions = [
        _normalize_chapter_question(q, quiz_type)
        for q in parsed if q.get("question_text")
    ]

    # Tag each question with chapter metadata
    for i, q in enumerate(questions):
        q["chapter_id"] = chapter.get("id")
        q["video_id"] = video_id
        q["order_idx"] = i

    return questions
