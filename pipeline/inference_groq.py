"""Groq-based inference engine — free API, fast, no GPU needed."""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path

from pipeline.models import AnswerResult, RetrievalResult
from pipeline.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GroqInference:
    """Generate educational answers using Groq's free API (Llama 4 Scout with vision)."""

    def __init__(self, model_name: str = "meta-llama/llama-4-scout-17b-16e-instruct"):
        self.model_name = model_name
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in environment")

        from groq import Groq
        self.client = Groq(api_key=api_key)
        logger.info("GroqInference ready with model=%s (vision-enabled)", model_name)

    def generate_answer(
        self,
        retrieval_result: RetrievalResult,
        max_new_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> AnswerResult:
        # Build context from retrieved segments
        context_parts = []
        for ctx in retrieval_result.contexts:
            seg = ctx.segment
            mins = int(seg.start_time // 60)
            secs = int(seg.start_time % 60)
            context_parts.append(
                f"[{mins}:{secs:02d} - {int(seg.end_time//60)}:{int(seg.end_time%60):02d}] "
                f"(relevance: {ctx.relevance_score:.0%})\n{seg.transcript_text}"
            )
        context_text = "\n\n---\n\n".join(context_parts)

        # Build multimodal content (text + images)
        user_content = []
        user_content.append({
            "type": "text",
            "text": (
                f"Here are relevant segments from the lecture video:\n\n"
                f"{context_text}\n\n---\n\n"
                f"Student question: {retrieval_result.query}\n\n"
                f"Please provide a clear, detailed educational answer based on the lecture content "
                f"and any visual information from the video frames provided."
            ),
        })

        # Attach up to 4 frames from retrieved segments
        frame_count = 0
        for ctx in retrieval_result.contexts:
            if frame_count >= 4:
                break
            for fp in ctx.segment.frame_paths:
                if frame_count >= 4:
                    break
                p = Path(fp)
                if p.exists() and p.stat().st_size > 0:
                    try:
                        img_b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                        user_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        })
                        frame_count += 1
                    except Exception as e:
                        logger.warning("Failed to read frame %s: %s", fp, e)

        if frame_count > 0:
            logger.info("Attached %d frames to Groq request", frame_count)

        t0 = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=max_new_tokens,
            temperature=temperature,
        )
        elapsed = time.perf_counter() - t0

        raw = response.choices[0].message.content
        answer_text = raw.strip() if raw else "No answer generated."

        sources = [
            {
                "start_time": ctx.segment.start_time,
                "end_time": ctx.segment.end_time,
                "relevance_score": ctx.relevance_score,
            }
            for ctx in retrieval_result.contexts
        ]

        return AnswerResult(
            question=retrieval_result.query,
            answer=answer_text,
            video_id=retrieval_result.video_id,
            sources=sources,
            quality_scores=None,
            model_name=f"groq/{self.model_name}",
            generation_time_seconds=round(elapsed, 2),
        )
