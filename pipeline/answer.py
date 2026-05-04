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

logger = logging.getLogger(__name__)


class _StreamMidwayError(Exception):
    """Raised when a streaming backend fails AFTER it has already emitted at
    least one token. Signals the orchestrator NOT to fall back to another
    backend (because the user has already seen partial output)."""

_SYSTEM_PROMPT = """\
You are an expert AI teaching assistant. A student is watching a lecture \
video and has paused at {timestamp_fmt} to ask a question. Answer clearly \
and pedagogically, using the provided context.

Rules:
1. CLARITY is your top priority — explain every technical term simply.
2. Reference what's shown on screen when relevant.
3. Use examples, analogies, and step-by-step breakdowns.
4. Only state facts supported by the lecture content provided.
5. If the question isn't related to the video, politely say so.

Length:
- Default to SHORT, focused answers (2–5 sentences, or a tiny bullet list). \
Resist the urge to over-explain.
- Only give a long, detailed walkthrough if the student EXPLICITLY asks for \
it (e.g. "explain in detail", "step by step", "go deep", "long form", \
"derivation").

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
    groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
    gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")

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

    # ── Try Groq first, then Gemini ───────────────────────────────
    if groq_key:
        try:
            answer, model_name, gen_time = _call_groq(
                system_prompt, context_text, question, images_b64, groq_key,
            )
            return {
                "answer": answer,
                "model_name": model_name,
                "generation_time": gen_time,
                "sources": sources,
            }
        except Exception as exc:
            logger.warning("Groq failed, falling back to Gemini: %s", exc)
            _last_error = exc

    if gemini_key:
        try:
            answer, model_name, gen_time = _call_gemini(
                system_prompt, context_text, question, images_b64, gemini_key,
            )
            return {
                "answer": answer,
                "model_name": model_name,
                "generation_time": gen_time,
                "sources": sources,
            }
        except Exception as exc:
            logger.error("Gemini also failed: %s", exc)
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
    model: str = "gemini-2.5-flash",
) -> tuple[str, str, float]:
    """Call Gemini API using google-genai SDK. Returns (answer, model_name, elapsed)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    parts = [types.Part.from_text(text=f"{system_prompt}\n\n{context_text}\n\nQUESTION: {question}")]

    for b64_str in images_b64:
        import base64 as b64mod
        parts.append(types.Part.from_bytes(data=b64mod.b64decode(b64_str), mime_type="image/jpeg"))

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


# ── Streaming variants ──────────────────────────────────────────
# Token-by-token streaming so the frontend can render the answer as it's
# generated (ChatGPT-style live typing) instead of waiting for the full
# response. Same context-assembly logic as ``generate_answer`` above.


def _build_context(
    question: str,
    timestamp: float,
    retrieval_result: dict,
    live_frame_path: str | None,
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
    if live_frame_path:
        b64 = _read_image_b64(live_frame_path)
        if b64:
            images_b64.append(b64)
    for kf in relevant_keyframes:
        if len(images_b64) >= 4:
            break
        kf_file = kf.get("file", "")
        if kf_file:
            b64 = _read_image_b64(kf_file)
            if b64:
                images_b64.append(b64)

    sources = [
        {
            "start_time": ch.get("start_time", 0),
            "end_time": ch.get("end_time", 0),
            "relevance_score": ch.get("similarity", 0),
        }
        for ch in ranked_chunks[:10]
    ]
    return context_text, images_b64, sources


def generate_answer_stream(
    question: str,
    video_id: str,
    timestamp: float,
    retrieval_result: dict,
    live_frame_path: str | None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> Iterator[dict]:
    """Streaming counterpart of :func:`generate_answer`.

    Yields a sequence of dict events:
    - ``{"type": "token", "text": "..."}`` for each text fragment
    - ``{"type": "end", "model_name": "...", "generation_time": <float>}`` once

    The orchestrator wraps these in SSE frames. Falls back from Groq → Gemini
    only if Groq fails BEFORE emitting any tokens (so we never double-emit).
    """
    groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
    gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")

    context_text, images_b64, _sources = _build_context(
        question, timestamp, retrieval_result, live_frame_path,
    )
    system_prompt = _SYSTEM_PROMPT.format(timestamp_fmt=_fmt_timestamp(timestamp))

    _last_error: Exception | None = None

    if groq_key:
        try:
            yield from _stream_groq(system_prompt, context_text, question, images_b64, groq_key)
            return
        except _StreamMidwayError:
            # Tokens already sent — re-raise so the caller surfaces an error
            # to the client instead of restarting from scratch with Gemini.
            raise
        except Exception as exc:
            logger.warning("Groq stream failed before any tokens, falling back to Gemini: %s", exc)
            _last_error = exc

    if gemini_key:
        try:
            yield from _stream_gemini(system_prompt, context_text, question, images_b64, gemini_key)
            return
        except _StreamMidwayError:
            raise
        except Exception as exc:
            logger.error("Gemini stream also failed: %s", exc)
            _last_error = exc

    if not groq_key and not gemini_key:
        raise RuntimeError("No LLM API key available (need GROQ_API_KEY or GEMINI_API_KEY)")
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


def _stream_gemini(
    system_prompt: str,
    context_text: str,
    question: str,
    images_b64: list[str],
    api_key: str,
    model: str = "gemini-2.5-flash",
) -> Iterator[dict]:
    """Stream tokens from Gemini using the google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

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
