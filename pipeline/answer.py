"""Answer generation: assemble context and send to VLM.

Context assembly combines:
1. Live frame — ephemeral frame at the exact question timestamp
2. Ranked chunks — 10-sec transcript windows near the timestamp
3. Stored keyframes — pre-indexed frames linked to chunks
4. Lecture digest — comprehensive lecture description

Primary LLM: Groq (Llama 4 Scout, vision-capable)
Fallback: Gemini 2.0 Flash
"""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import Iterator

from pipeline.model_prefs import gemini_model, openrouter_override
from pipeline.usage import record as _record_usage

logger = logging.getLogger(__name__)


class _StreamMidwayError(Exception):
    """Raised when a streaming backend fails AFTER it has already emitted at
    least one token. Signals the orchestrator NOT to fall back to another
    backend (because the user has already seen partial output)."""

_SYSTEM_PROMPT = """\
You are an expert AI teaching assistant. A student is watching a lecture \
video and has paused at {timestamp_fmt} to ask a question. Answer clearly, \
concisely, and pedagogically, using ONLY the provided context.

FORMAT EVERY ANSWER (default = short, skimmable bullet points — never long paragraphs):
- Begin with a difficulty tag in square brackets — [Beginner], [Intermediate], \
or [Advanced] — followed by a 1-2 line TL;DR of the answer.
- Then give the direct answer as a few tight bullets in plain, layman's language.
- Prefer ONE concrete real-life analogy (Indian/everyday context only when it \
fits naturally — never force it).
- On the first use of any jargon/technical term, add a short meaning plus its \
ETYMOLOGICAL root (e.g. Greek/Latin origin) so the name itself becomes a memory \
hook. If the origin is uncertain, say so — never invent it.

DEPTH ON DEMAND (stay SHORT by default):
- Do NOT dump everything every time. Add a deeper section ONLY when it genuinely \
helps this question, or when the student asks for more (e.g. "explain in detail", \
"go deep", "deep dive"). When warranted, add clearly-labelled bullet sections in \
this order:
  - Technical depth with 2-3 varied examples (different contexts / edge cases / applications).
  - 2-3 common misconceptions.
  - One mnemonic, acronym, or 1-line story to retain the core idea.
  - Exam angle: how it's typically tested (MCQ traps, conceptual vs numerical, \
common patterns) — only if exam-relevant.
  - Research frontier: where it stands, open debates, key terms/papers — only \
for academic/technical topics.
  - 3-5 Bloom's-taxonomy questions (Remember, Understand, Apply, Analyse, \
Evaluate). Put ALL their answers together at the very END as short keywords only.
  - 3-5 quick revision Q&A pairs.
  - 1-2 related follow-up topics worth asking next.

GROUNDING & SCOPE:
- State only facts supported by the provided lecture context; reference what's \
shown on screen when relevant.
- If the question isn't related to the video, politely say so.
- Refer to a keyframe image only when it actually clarifies the point.
- Each attached on-screen frame is labelled with its exact timestamp. When asked \
WHEN or "at which moment" something VISUAL happens (drawing a curve, writing on \
the board, a specific slide), answer with those frame timestamp(s); if none match \
well, say so honestly rather than guessing.

Math formatting:
- For inline math, wrap with single dollar signs: $x^2 + y^2$
- For block / displayed math, wrap with double dollar signs on their own lines:
  $$ \\sqrt{{\\frac{{\\sum_{{i=1}}^{{n}} (y_i - \\hat{{y}}_i)^2}}{{n}}}} $$
- Do NOT use \\( \\) or \\[ \\] delimiters.
- Do NOT escape backslashes (write `\\frac`, not `\\\\frac`).\
"""


def _fmt_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _read_image_b64(path: str) -> str | None:
    """Read an image (file path OR public URL) and return base64 string, or None on failure."""
    if not path:
        return None
    # URL → fetch via HTTP
    if path.startswith(("http://", "https://")):
        try:
            import urllib.request

            with urllib.request.urlopen(path, timeout=8) as resp:
                data = resp.read()
            if not data:
                return None
            return base64.b64encode(data).decode("utf-8")
        except Exception as exc:
            logger.warning("Failed to fetch image URL %s: %s", path[:80], exc)
            return None
    # Local file path
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        return None
    try:
        return base64.b64encode(p.read_bytes()).decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to read image %s: %s", path, exc)
        return None


def generate_answer(
    question: str,
    video_id: str,
    timestamp: float,
    retrieval_result: dict,
    live_frame_path: str | None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> dict:
    """Generate an educational answer from assembled context.

    Returns
    -------
    dict with keys: ``answer``, ``model_name``, ``generation_time``, ``sources``.
    """
    _last_error: Exception | None = None
    groq_key = groq_api_key if groq_api_key is not None else os.getenv("GROQ_API_KEY", "")
    gemini_key = gemini_api_key if gemini_api_key is not None else os.getenv("GEMINI_API_KEY", "")

    # ── Assemble text context ─────────────────────────────────────
    ranked_chunks = retrieval_result.get("ranked_chunks", [])
    digest = retrieval_result.get("digest", "")
    relevant_keyframes = retrieval_result.get("relevant_keyframes", [])

    context_lines: list[str] = []

    # Digest
    if digest:
        context_lines.append("[Lecture Digest]")
        context_lines.append(digest[:6000])  # cap to stay within context window
        context_lines.append("")

    # Ranked transcript chunks
    if ranked_chunks:
        context_lines.append(f"[Relevant Transcript (ranked by relevance to {_fmt_timestamp(timestamp)})]")
        for ch in ranked_chunks[:10]:
            st = ch.get("start_time", 0)
            et = ch.get("end_time", 0)
            text = ch.get("text", "")
            sim = ch.get("similarity", 0)
            context_lines.append(
                f"[{_fmt_timestamp(st)} - {_fmt_timestamp(et)}] (relevance: {sim:.0%})\n{text}"
            )
        context_lines.append("")

    context_text = "\n".join(context_lines)

    # ── Collect images ────────────────────────────────────────────
    images_b64: list[str] = []

    # Live frame first (most relevant)
    if live_frame_path:
        b64 = _read_image_b64(live_frame_path)
        if b64:
            images_b64.append(b64)

    # Stored keyframes from retrieval (up to 3 more)
    for kf in relevant_keyframes:
        if len(images_b64) >= 4:
            break
        kf_file = kf.get("file", "")
        if kf_file:
            b64 = _read_image_b64(kf_file)
            if b64:
                images_b64.append(b64)

    # ── Build sources list ────────────────────────────────────────
    sources = [
        {
            "start_time": ch.get("start_time", 0),
            "end_time": ch.get("end_time", 0),
            "relevance_score": ch.get("similarity", 0),
        }
        for ch in ranked_chunks[:10]
    ]

    # ── System prompt ─────────────────────────────────────────────
    system_prompt = _SYSTEM_PROMPT.format(timestamp_fmt=_fmt_timestamp(timestamp))

    # ── Try Gemini first, then OpenRouter (DeepSeek / Llama-Vision) ──
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    or_pref = openrouter_override("answers")  # set → user chose an OpenRouter model

    # If the user explicitly picked an OpenRouter model for answers, try it first.
    if or_pref and or_key:
        try:
            answer, model_name, gen_time = _call_openrouter(
                system_prompt, context_text, question, images_b64, or_key, model=or_pref,
            )
            return {
                "answer": answer,
                "model_name": model_name,
                "generation_time": gen_time,
                "sources": sources,
            }
        except Exception as exc:
            logger.warning("OpenRouter (user pref) failed, falling back: %s", exc)
            _last_error = exc

    if gemini_key:
        try:
            answer, model_name, gen_time = _call_gemini(
                system_prompt, context_text, question, images_b64, gemini_key,
                model=gemini_model("answers"),
            )
            return {
                "answer": answer,
                "model_name": model_name,
                "generation_time": gen_time,
                "sources": sources,
            }
        except Exception as exc:
            logger.warning("Gemini failed, falling back to OpenRouter: %s", exc)
            _last_error = exc

    if or_key:
        try:
            answer, model_name, gen_time = _call_openrouter(
                system_prompt, context_text, question, images_b64, or_key,
                model=or_pref or None,
            )
            return {
                "answer": answer,
                "model_name": model_name,
                "generation_time": gen_time,
                "sources": sources,
            }
        except Exception as exc:
            logger.error("OpenRouter also failed: %s", exc)
            _last_error = exc

    if not groq_key and not gemini_key:
        raise RuntimeError("No LLM API key available (need GROQ_API_KEY or GEMINI_API_KEY)")
    raise RuntimeError(f"All LLM backends failed. Last error: {_last_error}")


# ── Groq backend ─────────────────────────────────────────────────


def _call_groq(
    system_prompt: str,
    context_text: str,
    question: str,
    images_b64: list[str],
    api_key: str,
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
) -> tuple[str, str, float]:
    """Call Groq API with vision support. Returns (answer, model_name, elapsed)."""
    from groq import Groq

    client = Groq(api_key=api_key)

    user_content: list[dict] = []
    user_content.append({
        "type": "text",
        "text": f"{context_text}\n\n[Visual Context]\nSee attached lecture frames.\n\nQUESTION: {question}",
    })

    for b64 in images_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=4096,
        temperature=0.3,
    )
    elapsed = round(time.perf_counter() - t0, 2)

    raw = response.choices[0].message.content or ""
    return raw.strip(), f"groq/{model}", elapsed


# ── Gemini fallback ──────────────────────────────────────────────


def _call_gemini(
    system_prompt: str,
    context_text: str,
    question: str,
    images_b64: list[str],
    api_key: str,
    model: str = "gemini-flash-latest",
) -> tuple[str, str, float]:
    """Call Gemini API using google-genai SDK. Returns (answer, model_name, elapsed)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    parts = [types.Part.from_text(text=f"{system_prompt}\n\n{context_text}\n\nQUESTION: {question}")]

    for b64_str in images_b64:
        import base64 as b64mod
        parts.append(types.Part.from_bytes(data=b64mod.b64decode(b64_str), mime_type="image/jpeg"))

    _record_usage("gemini", model)
    t0 = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    elapsed = round(time.perf_counter() - t0, 2)

    return response.text.strip(), f"gemini/{model}", elapsed


# ── OpenRouter (DeepSeek / Llama-Vision) ────────────────────────
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OR_VISION_MODEL = "meta-llama/llama-3.2-11b-vision-instruct"
_OR_TEXT_MODEL = "deepseek/deepseek-chat"


def _openrouter_messages(system_prompt, context_text, question, images_b64):
    if images_b64:
        user_content = [{"type": "text", "text": f"{context_text}\n\nQUESTION: {question}"}]
        for b64 in images_b64:
            user_content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            )
    else:
        user_content = f"{context_text}\n\nQUESTION: {question}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def _call_openrouter(system_prompt, context_text, question, images_b64, api_key, model=None):
    """Non-streaming OpenRouter call. Tries FREE models first (0 credit cost),
    then the cheap paid model. Vision models when images are present."""
    import json
    import urllib.error
    import urllib.request

    from pipeline.model_prefs import (
        OR_FREE_TEXT_MODELS, OR_FREE_VISION_MODELS,
        OR_TEXT_PAID_FALLBACK, OR_VISION_PAID_FALLBACK,
    )

    if model:
        candidates = [model]
    elif images_b64:
        candidates = [*OR_FREE_VISION_MODELS, OR_VISION_PAID_FALLBACK]
    else:
        candidates = [*OR_FREE_TEXT_MODELS, OR_TEXT_PAID_FALLBACK]

    last_exc: Exception | None = None
    for m in candidates:
        body = json.dumps({
            "model": m,
            "messages": _openrouter_messages(system_prompt, context_text, question, images_b64),
            "max_tokens": 4096,
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(
            _OPENROUTER_URL, data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        try:
            r = json.load(urllib.request.urlopen(req, timeout=90))
            text = (r["choices"][0]["message"]["content"] or "").strip()
            if text:
                return text, f"openrouter/{m}", round(time.perf_counter() - t0, 2)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 402, 503):
                _record_usage("openrouter", m)
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    raise last_exc or RuntimeError("All OpenRouter models unavailable")


# ── Streaming variants ──────────────────────────────────────────
# Token-by-token streaming so the frontend can render the answer as it's
# generated (ChatGPT-style live typing) instead of waiting for the full
# response. Same context-assembly logic as ``generate_answer`` above.


def _build_context(
    question: str,
    timestamp: float,
    retrieval_result: dict,
    live_frame_path: str | None,
    point_mode: bool = False,
) -> tuple[str, list[str], list[dict]]:
    """Shared context assembly used by both blocking and streaming paths.

    Returns (context_text, images_b64, sources).
    """
    ranked_chunks = retrieval_result.get("ranked_chunks", [])
    digest = retrieval_result.get("digest", "")
    relevant_keyframes = retrieval_result.get("relevant_keyframes", [])

    context_lines: list[str] = []
    if digest:
        context_lines.append("[Lecture Digest]")
        context_lines.append(digest[:6000])
        context_lines.append("")
    if ranked_chunks:
        context_lines.append(
            f"[Relevant Transcript (ranked by relevance to {_fmt_timestamp(timestamp)})]"
        )
        for ch in ranked_chunks[:10]:
            st = ch.get("start_time", 0)
            et = ch.get("end_time", 0)
            text = ch.get("text", "")
            sim = ch.get("similarity", 0)
            context_lines.append(
                f"[{_fmt_timestamp(st)} - {_fmt_timestamp(et)}] (relevance: {sim:.0%})\n{text}"
            )
        context_lines.append("")
    context_text = "\n".join(context_lines)

    images_b64: list[str] = []
    frame_notes: list[str] = []  # tells the model WHEN each attached frame occurs
    if live_frame_path:
        b64 = _read_image_b64(live_frame_path)
        if b64:
            images_b64.append(b64)
            frame_notes.append(f"Frame {len(images_b64)}: at {_fmt_timestamp(timestamp)} (the current moment)")
    kf_sources: list[dict] = []
    for kf in relevant_keyframes:
        if len(images_b64) >= 4:
            break
        kf_ts = float(kf.get("timestamp", 0) or 0)
        # Point mode = "what's happening at THIS moment". Don't attach frames
        # from far away in the video — they make the model read OTHER boards and
        # mix in unrelated formulas. Keep only frames near the current moment.
        if point_mode and abs(kf_ts - timestamp) > 120:
            continue
        kf_file = kf.get("file", "")
        if not kf_file:
            continue
        b64 = _read_image_b64(kf_file)
        if not b64:
            continue
        images_b64.append(b64)
        kf_sim = float(kf.get("similarity", 0) or 0)
        frame_notes.append(f"Frame {len(images_b64)}: on-screen at {_fmt_timestamp(kf_ts)} (visual match {kf_sim:.0%})")
        kf_sources.append({"start_time": kf_ts, "end_time": kf_ts, "relevance_score": kf_sim})

    # Tell the model exactly WHEN each attached frame occurs so it can answer
    # "at which moment …" questions with real, clickable timestamps.
    if frame_notes:
        context_text += "\n[On-screen frames attached to this message]\n" + "\n".join(frame_notes) + "\n"

    sources = [
        {
            "start_time": ch.get("start_time", 0),
            "end_time": ch.get("end_time", 0),
            "relevance_score": ch.get("similarity", 0),
        }
        for ch in ranked_chunks[:10]
    ] + kf_sources
    return context_text, images_b64, sources


def generate_answer_stream(
    question: str,
    video_id: str,
    timestamp: float,
    retrieval_result: dict,
    live_frame_path: str | None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
    prefer: str = "auto",
    point_mode: bool = False,
) -> Iterator[dict]:
    """Streaming counterpart of :func:`generate_answer`.

    Yields a sequence of dict events:
    - ``{"type": "token", "text": "..."}`` for each text fragment
    - ``{"type": "end", "model_name": "...", "generation_time": <float>}`` once

    The orchestrator wraps these in SSE frames. Falls back from Groq → Gemini
    only if Groq fails BEFORE emitting any tokens (so we never double-emit).
    """
    groq_key = groq_api_key if groq_api_key is not None else os.getenv("GROQ_API_KEY", "")
    gemini_key = gemini_api_key if gemini_api_key is not None else os.getenv("GEMINI_API_KEY", "")

    context_text, images_b64, _sources = _build_context(
        question, timestamp, retrieval_result, live_frame_path, point_mode=point_mode,
    )
    system_prompt = _SYSTEM_PROMPT.format(timestamp_fmt=_fmt_timestamp(timestamp))

    _last_error: Exception | None = None

    or_key = os.getenv("OPENROUTER_API_KEY", "")
    or_pref = openrouter_override("answers")  # WHICH OpenRouter model (Advanced)

    def _try_groq() -> Iterator[dict]:
        yield from _stream_groq(system_prompt, context_text, question, images_b64, groq_key)

    def _try_gemini() -> Iterator[dict]:
        yield from _stream_gemini(
            system_prompt, context_text, question, images_b64, gemini_key,
            model=gemini_model("answers"),
        )

    def _try_openrouter() -> Iterator[dict]:
        yield from _stream_openrouter(
            system_prompt, context_text, question, images_b64, or_key, model=or_pref or None,
        )

    # The top-level "Answer model" choice decides the PROVIDER (and its order);
    # the Advanced per-feature dropdown decides WHICH model within a provider.
    # This keeps the two settings consistent instead of the override silently
    # winning over the radio.
    if prefer == "groq":
        plan = [("groq", bool(groq_key), _try_groq)]
    elif prefer == "gemini":
        plan = [("gemini", bool(gemini_key), _try_gemini)]
    elif prefer == "openrouter":
        plan = [("openrouter", bool(or_key), _try_openrouter),
                ("gemini", bool(gemini_key), _try_gemini)]
    else:  # auto: honor an OpenRouter model override first, then fast Groq, then Gemini
        plan = [("openrouter", bool(or_pref and or_key), _try_openrouter),
                ("groq", bool(groq_key), _try_groq),
                ("gemini", bool(gemini_key), _try_gemini),
                ("openrouter", bool(or_key), _try_openrouter)]

    for name, available, fn in plan:
        if not available:
            continue
        try:
            yield from fn()
            return
        except _StreamMidwayError:
            raise
        except Exception as exc:
            logger.warning("%s stream failed before tokens, trying next: %s", name, exc)
            _last_error = exc

    if not (groq_key or gemini_key or or_key):
        raise RuntimeError("No LLM API key available (add a Groq, Gemini or OpenRouter key in Settings)")
    raise RuntimeError(f"All LLM streaming backends failed. Last error: {_last_error}")


def _stream_groq(
    system_prompt: str,
    context_text: str,
    question: str,
    images_b64: list[str],
    api_key: str,
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
) -> Iterator[dict]:
    """Stream tokens from Groq's chat completions API."""
    from groq import Groq

    client = Groq(api_key=api_key)

    user_content: list[dict] = [{
        "type": "text",
        "text": f"{context_text}\n\n[Visual Context]\nSee attached lecture frames.\n\nQUESTION: {question}",
    }]
    for b64 in images_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    t0 = time.perf_counter()
    # Connection / setup errors here are pre-stream — outer code may fall back.
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=4096,
        temperature=0.3,
        stream=True,
    )

    yielded_any = False
    try:
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError):
                delta = None
            if delta:
                yielded_any = True
                yield {"type": "token", "text": delta}
    except Exception as exc:
        if yielded_any:
            raise _StreamMidwayError(f"Groq stream interrupted: {exc}") from exc
        raise

    elapsed = round(time.perf_counter() - t0, 2)
    yield {"type": "end", "model_name": f"groq/{model}", "generation_time": elapsed}


def _stream_openrouter(
    system_prompt: str,
    context_text: str,
    question: str,
    images_b64: list[str],
    api_key: str,
    model: str | None = None,
) -> Iterator[dict]:
    """Stream tokens from OpenRouter (OpenAI-compatible SSE). Tries FREE models
    first (0 credit cost), then the cheap paid model. Vision if images."""
    import json
    import urllib.error
    import urllib.request

    from pipeline.model_prefs import (
        OR_FREE_TEXT_MODELS, OR_FREE_VISION_MODELS,
        OR_TEXT_PAID_FALLBACK, OR_VISION_PAID_FALLBACK,
    )

    if model:
        candidates = [model]
    elif images_b64:
        candidates = [*OR_FREE_VISION_MODELS, OR_VISION_PAID_FALLBACK]
    else:
        candidates = [*OR_FREE_TEXT_MODELS, OR_TEXT_PAID_FALLBACK]

    last_exc: Exception | None = None
    for m in candidates:
        body = json.dumps({
            "model": m,
            "messages": _openrouter_messages(system_prompt, context_text, question, images_b64),
            "max_tokens": 4096,
            "temperature": 0.3,
            "stream": True,
        }).encode()
        req = urllib.request.Request(
            _OPENROUTER_URL, data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        yielded_any = False
        try:
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 402:
                # No OpenRouter credits — every other model will 402 the same
                # way. Stop immediately so we fall back (e.g. to Gemini) in
                # seconds instead of burning minutes retrying each free model.
                break
            if exc.code in (429, 503):
                continue  # rate-limited / model down → try next free model
            raise
        try:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except Exception:
                    delta = None
                if delta:
                    yielded_any = True
                    yield {"type": "token", "text": delta}
        except Exception as exc:  # noqa: BLE001
            if yielded_any:
                raise _StreamMidwayError(f"OpenRouter stream interrupted: {exc}") from exc
            last_exc = exc
            continue
        if yielded_any:
            elapsed = round(time.perf_counter() - t0, 2)
            yield {"type": "end", "model_name": f"openrouter/{m}", "generation_time": elapsed}
            return
    raise last_exc or RuntimeError("All OpenRouter models unavailable")


def _stream_gemini(
    system_prompt: str,
    context_text: str,
    question: str,
    images_b64: list[str],
    api_key: str,
    model: str = "gemini-flash-latest",
) -> Iterator[dict]:
    """Stream tokens from Gemini using the google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    _record_usage("gemini", model)

    parts = [types.Part.from_text(text=f"{system_prompt}\n\n{context_text}\n\nQUESTION: {question}")]
    for b64_str in images_b64:
        import base64 as b64mod
        parts.append(types.Part.from_bytes(data=b64mod.b64decode(b64_str), mime_type="image/jpeg"))

    t0 = time.perf_counter()
    stream = client.models.generate_content_stream(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    yielded_any = False
    try:
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yielded_any = True
                yield {"type": "token", "text": text}
    except Exception as exc:
        if yielded_any:
            raise _StreamMidwayError(f"Gemini stream interrupted: {exc}") from exc
        raise

    elapsed = round(time.perf_counter() - t0, 2)
    yield {"type": "end", "model_name": f"gemini/{model}", "generation_time": elapsed}
