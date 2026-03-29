"""Quality evaluation: score answers on Clarity / ECT / UPT using Likert scales."""

from __future__ import annotations

import json
import logging
import re

from pipeline.models import QualityScores
from pipeline.prompts import EVAL_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


def _parse_scores(text: str) -> QualityScores:
    """Extract QualityScores from LLM JSON output, with fallback regex parsing."""
    # Try direct JSON parse first
    try:
        # Find the first JSON object in the response
        match = re.search(r"\{[^}]+\}", text)
        if match:
            data = json.loads(match.group())
            return QualityScores(
                clarity=float(data["clarity"]),
                ect=float(data["ect"]),
                upt=float(data["upt"]),
            )
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # Fallback: look for "clarity": N patterns
    clarity = _extract_number(text, "clarity")
    ect = _extract_number(text, "ect")
    upt = _extract_number(text, "upt")

    if clarity and ect and upt:
        return QualityScores(clarity=clarity, ect=ect, upt=upt)

    raise ValueError(f"Could not parse quality scores from LLM output: {text!r}")


def _extract_number(text: str, key: str) -> float | None:
    match = re.search(rf'"{key}"\s*:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    return float(match.group(1)) if match else None


class QualityEvaluator:
    """Score answers on Clarity/ECT/UPT using the EduVidQA Likert scales."""

    def __init__(self, method: str = "hf_inference") -> None:
        """
        Args:
            method: One of
                - ``"hf_inference"``: HuggingFace free Inference API (Qwen2.5-72B-Instruct)
                - ``"local"``: Use the local Qwen2.5-VL-7B (less accurate, no API needed)
                - ``"groq"``: Groq free API (Llama 3.3 70B, fast)
        """
        if method not in ("hf_inference", "local", "groq"):
            raise ValueError(f"Unknown evaluation method: {method}")
        self.method = method
        self._client = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def score(self, question: str, answer: str) -> QualityScores:
        """Score an answer on Clarity/ECT/UPT. Returns QualityScores."""
        prompt = EVAL_PROMPT_TEMPLATE.format(question=question, answer=answer)

        if self.method == "hf_inference":
            raw = self._call_hf(prompt)
        elif self.method == "groq":
            raw = self._call_groq(prompt)
        elif self.method == "local":
            raw = self._call_local(prompt)
        else:
            raise ValueError(self.method)

        return _parse_scores(raw)

    # ------------------------------------------------------------------ #
    # Backend implementations
    # ------------------------------------------------------------------ #

    def _call_hf(self, prompt: str) -> str:
        """Use HuggingFace free Inference API with Qwen2.5-72B-Instruct."""
        import os

        from huggingface_hub import InferenceClient

        token = os.environ.get("HF_TOKEN", "")
        client = InferenceClient(
            model="Qwen/Qwen2.5-72B-Instruct",
            token=token or None,
        )
        response = client.text_generation(
            prompt,
            max_new_tokens=100,
            temperature=0.1,
        )
        return response

    def _call_groq(self, prompt: str) -> str:
        """Use Groq free API with Llama 3.3 70B."""
        import os

        import httpx

        api_key = os.environ["GROQ_API_KEY"]
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_local(self, prompt: str) -> str:
        """Use the locally-loaded Qwen2.5-VL-7B for evaluation (less accurate)."""
        from pipeline.inference import QwenInference

        if self._client is None:
            self._client = QwenInference(quantize_4bit=True)

        from pipeline.models import RetrievedContext, RetrievalResult, VideoSegment

        # Wrap the eval prompt as a single-segment retrieval result
        dummy_result = RetrievalResult(
            query=prompt,
            video_id="eval",
            contexts=[
                RetrievedContext(
                    segment=VideoSegment(
                        video_id="eval",
                        segment_index=0,
                        start_time=0,
                        end_time=0,
                        transcript_text="",
                        frame_paths=[],
                    ),
                    relevance_score=1.0,
                    rank=1,
                )
            ],
            total_segments=1,
        )
        result = self._client.generate_answer(
            dummy_result, max_new_tokens=100, temperature=0.1
        )
        return result.answer
