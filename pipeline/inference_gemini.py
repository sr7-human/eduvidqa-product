"""Gemini-based inference engine — best quality, free tier, native video understanding."""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path

from pipeline.models import AnswerResult, RetrievalResult
from pipeline.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GeminiInference:
    """Generate educational answers using Google Gemini 2.5 Flash."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set. Get one free: https://aistudio.google.com/apikey")

        from google import genai
        self.client = genai.Client(api_key=api_key)
        logger.info("GeminiInference ready with model=%s", model_name)

    def generate_answer(
        self,
        retrieval_result: RetrievalResult,
        max_new_tokens: int = 4096,
        temperature: float = 0.3,
        timestamp: float | None = None,
        video_data_dir: str = "./data",
    ) -> AnswerResult:
        from PIL import Image

        # Build context from retrieved segments
        context_parts = []
        for ctx in retrieval_result.contexts:
            seg = ctx.segment
            mins = int(seg.start_time // 60)
            secs = int(seg.start_time % 60)
            context_parts.append(
                f"[{mins}:{secs:02d} - {int(seg.end_time // 60)}:{int(seg.end_time % 60):02d}] "
                f"(relevance: {ctx.relevance_score:.0%})\n{seg.transcript_text}"
            )
        context_text = "\n\n---\n\n".join(context_parts)

        # Build parts list: text + images
        parts = []

        # 1. First, attach frames at the EXACT timestamp the user asked about
        timestamp_frames = 0
        if timestamp is not None:
            video_id = retrieval_result.video_id
            frames_dir = Path(video_data_dir) / video_id / "frames"
            if frames_dir.exists():
                # Find frames closest to the timestamp (within ±10 seconds)
                all_frames = sorted(frames_dir.glob("frame_*.jpg"))
                for fp in all_frames:
                    try:
                        # Parse timestamp from filename: frame_01442.0s.jpg
                        fname = fp.stem  # frame_01442.0s
                        ts_str = fname.replace("frame_", "").replace("s", "")
                        frame_ts = float(ts_str)
                        if abs(frame_ts - timestamp) <= 10:
                            img = Image.open(str(fp))
                            parts.append(img)
                            timestamp_frames += 1
                            logger.info("Attached timestamp frame: %s (ts=%.1f, target=%.1f)", fp.name, frame_ts, timestamp)
                    except (ValueError, Exception) as e:
                        continue

        # 2. Add text + possibly RAG frames
        if timestamp_frames > 0 and timestamp is not None:
            # We have exact frames — prioritize visual, transcript as backup
            parts.append(
                f"Student question: {retrieval_result.query}\n\n"
                f"I have attached {timestamp_frames} frame(s) from timestamp "
                f"{int(timestamp//60)}:{int(timestamp%60):02d} of the lecture video.\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Look at the frames CAREFULLY\n"
                f"2. Describe EXACTLY what you see — every word, equation, diagram on the board/screen\n"
                f"3. Then explain each item using your knowledge\n"
                f"4. Do NOT make up content that is not visible in the frames\n\n"
                f"For additional context, here is what the professor is saying around this timestamp:\n\n"
                f"{context_text}"
            )
            rag_frame_count = 0  # skip RAG frames
        else:
            # No timestamp frames — use RAG text + frames
            parts.append(
                f"Here are relevant segments from the lecture video:\n\n"
                f"{context_text}\n\n---\n\n"
                f"Student question: {retrieval_result.query}\n\n"
                f"Provide a clear, detailed educational answer based on the lecture content."
            )
            rag_frame_count = 0
            max_rag_frames = 4
            for ctx in retrieval_result.contexts:
                if rag_frame_count >= max_rag_frames:
                    break
                for fp in ctx.segment.frame_paths:
                    if rag_frame_count >= max_rag_frames:
                        break
                    p = Path(fp)
                    if p.exists() and p.stat().st_size > 0:
                        try:
                            img = Image.open(str(p))
                            parts.append(img)
                            rag_frame_count += 1
                        except Exception as e:
                            logger.warning("Failed to read frame %s: %s", fp, e)

        total_frames = timestamp_frames + rag_frame_count
        logger.info("Sending %d frames to Gemini (%d from timestamp, %d from RAG)", total_frames, timestamp_frames, rag_frame_count)

        t0 = time.perf_counter()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=parts,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "max_output_tokens": max_new_tokens,
                "temperature": temperature,
            },
        )
        elapsed = time.perf_counter() - t0

        answer_text = response.text.strip() if response.text else "No answer generated."

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
            model_name=f"gemini/{self.model_name}",
            generation_time_seconds=round(elapsed, 2),
        )
