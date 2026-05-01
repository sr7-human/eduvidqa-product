"""Generate MCQ quiz questions from lecture content via LLM.

Primary: Groq Llama 3.3 70B. Fallback: Gemini 2.0 Flash.
"""
from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

QUIZ_PROMPT = """Based on this lecture content near timestamp {timestamp}:

{context}

Generate {count} multiple-choice questions. Each must:
- Test understanding, not memorization
- Have exactly 4 options (A, B, C, D)
- Have exactly one correct answer

Return ONLY a JSON array:
[{{"question_text": "...", "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A", "explanation": "...", "difficulty": "medium"}}]"""


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
    """Try direct json.loads, fallback to regex extraction."""
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
    raise ValueError(f"Could not parse JSON array from LLM response: {text[:200]}")


def _normalize_question(q: dict) -> dict:
    """Ensure required keys + safe defaults."""
    return {
        "question_text": str(q.get("question_text", "")).strip(),
        "options": list(q.get("options", [])),
        "correct_answer": str(q.get("correct_answer", "A")).strip()[:1].upper() or "A",
        "explanation": str(q.get("explanation", "")).strip(),
        "difficulty": str(q.get("difficulty", "medium")).strip().lower() or "medium",
    }


def _call_groq(prompt: str, api_key: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content or ""


def _call_gemini(prompt: str, api_key: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[types.Part.from_text(text=prompt)],
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=2000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text or ""


def generate_quiz_questions(
    video_id: str,
    timestamp: float,
    chunks: list[dict],
    count: int = 3,
) -> list[dict]:
    """Generate MCQ questions from chunks near a timestamp."""
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
