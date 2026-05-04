"""Generate MCQ quiz questions from lecture content via LLM.

Primary: Groq Llama 3.3 70B. Fallback: Gemini 2.0 Flash.
"""
from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

QUIZ_PROMPT = """You are a quiz designer for an educational lecture video. Based on this lecture content near timestamp {timestamp}:

{context}

Generate exactly {count} multiple-choice questions covering Bloom's taxonomy levels in this distribution:
  - 1 question  at level "remember"   (recall a single key fact, definition, or term)
  - 1 question  at level "understand" (explain or paraphrase one core idea)
  - 3 questions at level "apply"      (use the concept in a NEW situation or worked example)
  - 3 questions at level "analyse"    (compare, contrast, break down components, identify cause/effect, spot which assumption breaks)
  - 2 questions at level "evaluate"   (judge, critique, justify a choice between alternatives based on criteria)

Do NOT include any "create" level questions.

Focus most of your effort on the higher-order questions (apply, analyse, evaluate). The remember/understand questions should be quick warm-ups; the rest should make the learner actually think.

Each question must:
- Be self-contained (do not reference "the video", "the lecturer", or "the lecture")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Test the targeted cognitive level genuinely (an analyse-level Q must require analysis, not recall)

Return ONLY a JSON array of {count} objects in this exact shape:
[{{"question_text": "...",
   "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A",
   "explanation": "why the correct answer is correct",
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


def _normalize_question(q: dict) -> dict:
    """Ensure required keys + safe defaults."""
    bloom = str(q.get("bloom_level", "understand")).strip().lower() or "understand"
    if bloom not in {"remember", "understand", "apply", "analyse", "analyze", "evaluate"}:
        bloom = "understand"
    if bloom == "analyze":
        bloom = "analyse"
    return {
        "question_text": str(q.get("question_text", "")).strip(),
        "options": list(q.get("options", [])),
        "correct_answer": str(q.get("correct_answer", "A")).strip()[:1].upper() or "A",
        "explanation": str(q.get("explanation", "")).strip(),
        "difficulty": str(q.get("difficulty", "medium")).strip().lower() or "medium",
        "bloom_level": bloom,
    }


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
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
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
    prompt = QUIZ_PROMPT.format(timestamp=f"{timestamp:.0f}s", context=context, count=count)

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
    return [_normalize_question(q) for q in parsed if q.get("question_text")]


# ── Multi-checkpoint batched generation ──────────────────────────

MULTI_QUIZ_PROMPT = """You are a quiz designer for an educational lecture video.
You will generate quizzes for {n_checkpoints} different checkpoints from the same lecture, in a single response.

For EACH checkpoint, generate exactly {count_per_cp} multiple-choice questions with this Bloom distribution:
  - 1 question  at level "remember"   (recall a single key fact, definition, or term)
  - 1 question  at level "understand" (explain or paraphrase one core idea)
  - 3 questions at level "apply"      (use the concept in a NEW situation or worked example)
  - 3 questions at level "analyse"    (compare, contrast, break down components, identify cause/effect)
  - 2 questions at level "evaluate"   (judge, critique, justify a choice based on criteria)

Do NOT include any "create" level questions. Focus most of your effort on apply/analyse/evaluate.

Each question must:
- Be self-contained (do not reference "the video", "the lecturer", or "the lecture")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Test the targeted cognitive level genuinely

Lecture content per checkpoint:
{checkpoints_block}

Return ONE FLAT JSON array containing ALL {total_questions} questions across all checkpoints. Each question MUST include a `checkpoint_timestamp` field with the exact timestamp number from the matching checkpoint header above:

[
  {{"checkpoint_timestamp": 30,
    "question_text": "...",
    "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
    "correct_answer": "A",
    "explanation": "...",
    "difficulty": "medium",
    "bloom_level": "apply"}},
  ...{total_questions} total entries...
]

Return ONLY the JSON array, no other text."""


def generate_quizzes_for_checkpoints(
    video_id: str,
    checkpoint_timestamps: list[float],
    chunks: list[dict],
    count_per_cp: int = 10,
) -> dict[float, list[dict]]:
    """Generate quizzes for MULTIPLE checkpoints in a SINGLE LLM call.

    Returns a mapping of {timestamp: [questions]}. Falls back to per-checkpoint
    generation if the batched call fails or returns wrong count.
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

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    raw = ""
    last_err: Exception | None = None
    # 10 questions ≈ 2500 tokens with explanations + JSON overhead;
    # multiply by checkpoints + add buffer for the outer wrapper structure
    max_tokens = max(15000, 3500 * len(checkpoint_timestamps))
    if groq_key:
        try:
            raw = _call_groq(prompt, groq_key, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq multi-quiz failed, falling back to Gemini: %s", exc)
            last_err = exc
    if not raw and gemini_key:
        try:
            raw = _call_gemini(prompt, gemini_key, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini multi-quiz also failed: %s", exc)
            last_err = exc

    out: dict[float, list[dict]] = {ts: [] for ts in checkpoint_timestamps}
    if raw:
        try:
            parsed = _parse_json_array(raw)
            # Each item is a question with checkpoint_timestamp field
            for entry in parsed:
                if not isinstance(entry, dict) or not entry.get("question_text"):
                    continue
                ts_val = entry.get("checkpoint_timestamp")
                if not isinstance(ts_val, (int, float)):
                    continue
                # Snap to nearest expected checkpoint
                best = min(checkpoint_timestamps, key=lambda t: abs(t - float(ts_val)))
                out[best].append(_normalize_question(entry))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse batched quiz response: %s", exc)

    # Fill in any missing checkpoints with per-checkpoint generation as fallback
    missing = [ts for ts in checkpoint_timestamps if ts not in out or not out[ts]]
    if missing:
        if out:
            logger.info(
                "Batched quiz returned %d/%d; falling back per-checkpoint for %d missing",
                len(checkpoint_timestamps) - len(missing), len(checkpoint_timestamps), len(missing),
            )
        else:
            logger.warning("Batched quiz returned 0 entries (%s); falling back per-checkpoint", last_err)
        for ts in missing:
            try:
                out[ts] = generate_quiz_questions(video_id, ts, chunks, count=count_per_cp)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fallback quiz gen at %.0fs failed: %s", ts, exc)
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

NATURE — CURIOSITY-TRIGGERING / PREDICTION-STYLE:
- Frame questions as "What do you think…", "Which of these would…", "Before watching, predict…"
- Target prior knowledge the learner MIGHT have from everyday experience
- Getting it wrong is expected and fine — that's the point

DIFFICULTY: Easy to Medium only. The learner hasn't seen this content yet.
BLOOM DISTRIBUTION:
  - {count_remember} at level "remember" (prior knowledge recall)
  - {count_understand} at level "understand" (intuitive reasoning)

Each question must:
- Be self-contained (no references to "the video" or "the lecturer")
- Have exactly 4 options labelled "A: ...", "B: ...", "C: ...", "D: ..."
- Have exactly one correct answer
- Include `option_explanations` — an object with keys "A","B","C","D"
  - For the CORRECT option: 1-2 sentences explaining why it's right, citing the lesson content
  - For each WRONG option: 1-2 sentences explaining why it's wrong AND naming the specific misconception if applicable
  - Do NOT just say "this is incorrect". Always explain WHY.

Return ONLY a JSON array:
[{{"question_text": "...",
   "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A",
   "explanation": "short reason the correct answer is correct",
   "option_explanations": {{"A": "Correct because...", "B": "Wrong because...", "C": "Wrong because...", "D": "Wrong because..."}},
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
    base = _normalize_question(q)
    base["quiz_type"] = quiz_type

    # option_explanations
    oe = q.get("option_explanations")
    if isinstance(oe, dict):
        base["option_explanations"] = {
            k: str(v).strip() for k, v in oe.items() if k in ("A", "B", "C", "D") and v
        }
        # Derive legacy explanation from correct answer's explanation
        correct = base["correct_answer"]
        if correct in base["option_explanations"]:
            base["explanation"] = base["option_explanations"][correct]
    else:
        base["option_explanations"] = None

    # misconception_tags — extract from distractor explanations if LLM included them
    tags = q.get("misconception_tags")
    if isinstance(tags, list):
        base["misconception_tags"] = [str(t).strip() for t in tags if t]
    else:
        base["misconception_tags"] = None

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
    """Compute target chapter count from video duration. Cap at 8."""
    return max(1, min(8, round(duration_minutes / 12)))


def generate_chapter_quizzes(
    video_id: str,
    chapter: dict,
    chunks: list[dict],
    quiz_type: str,
    count: int = 5,
    mid_recall_timestamp: float | None = None,
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

    prompt = CHAPTER_QUIZ_PROMPTS[quiz_type].format(
        chapter_title=title,
        context=context,
        count=count,
        **bloom_counts,
    )

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    raw = ""
    last_err: Exception | None = None
    max_tokens = max(8000, 1500 * count)

    if groq_key:
        try:
            raw = _call_groq(prompt, groq_key, max_tokens=max_tokens)
        except Exception as exc:
            logger.warning("Groq chapter quiz failed: %s", exc)
            last_err = exc

    if not raw and gemini_key:
        try:
            raw = _call_gemini(prompt, gemini_key, max_tokens=max_tokens)
        except Exception as exc:
            logger.error("Gemini chapter quiz also failed: %s", exc)
            last_err = exc

    if not raw:
        raise RuntimeError(f"All LLM providers failed for chapter quiz: {last_err}")

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
