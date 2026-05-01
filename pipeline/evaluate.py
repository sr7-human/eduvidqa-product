"""Quality scoring v2: score answers on Clarity / ECT / UPT.

Uses Groq Llama 3.3 70B (text-only, fast) as the judge model.
Mirrors the EduVidQA paper's evaluation methodology.
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_SCORING_PROMPT = """\
Rate the following answer to a student's question on three scales (1-5):

1. CLARITY (1-5): Is the answer clear, well-organized, and free of unnecessary jargon?
   1=jargon-filled, incoherent | 5=crystal clear, beginner-friendly

2. ECT (1-5): Does the answer Encourage Critical Thinking?
   1=purely factual | 5=challenges assumptions, invites deeper exploration

3. UPT (1-5): Does the answer Use Pedagogical Techniques?
   1=no examples | 5=rich examples, analogies, scaffolding, step-by-step

Question: {question}
Answer: {answer}

Respond ONLY with JSON: {{"clarity": X, "ect": X, "upt": X}}\
"""


def _parse_scores(text: str) -> dict:
    """Extract scores from LLM output. Tries JSON first, then regex."""
    # Direct JSON parse
    try:
        match = re.search(r"\{[^}]+\}", text)
        if match:
            data = json.loads(match.group())
            return {
                "clarity": float(data["clarity"]),
                "ect": float(data["ect"]),
                "upt": float(data["upt"]),
            }
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # Regex fallback
    scores = {}
    for key in ("clarity", "ect", "upt"):
        m = re.search(rf'"{key}"\s*:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if m:
            scores[key] = float(m.group(1))

    if len(scores) == 3:
        return scores

    raise ValueError(f"Could not parse quality scores from: {text!r}")


def score_answer(
    question: str,
    answer: str,
    groq_api_key: str | None = None,
) -> dict:
    """Score an answer on Clarity/ECT/UPT using Groq Llama 3.3 70B.

    Returns
    -------
    dict : ``{"clarity": float, "ect": float, "upt": float}``
        Each value 1-5.
    """
    api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set — cannot score answer")

    from groq import Groq

    client = Groq(api_key=api_key)
    prompt = _SCORING_PROMPT.format(question=question, answer=answer)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.1,
    )

    raw = response.choices[0].message.content or ""
    return _parse_scores(raw)
