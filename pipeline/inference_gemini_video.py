"""Gemini Video inference — uploads FULL video to Gemini for native video understanding."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from pipeline.models import AnswerResult, RetrievalResult
from pipeline.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GeminiVideoInference:
    """Upload full video to Gemini and ask questions with native video understanding."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        from google import genai
        self.client = genai.Client(api_key=api_key)
        self._uploaded_videos: dict[str, object] = {}  # video_id -> genai File
        logger.info("GeminiVideoInference ready (model=%s)", model_name)

    def _ensure_video_uploaded(self, video_id: str, data_dir: str):  # type: ignore[return]
        """Upload video to Gemini Files API if not already uploaded."""
        if video_id in self._uploaded_videos:
            try:
                f = self._uploaded_videos[video_id]
                f = self.client.files.get(name=f.name)  # type: ignore[attr-defined]
                if f.state and f.state.name == "ACTIVE":  # type: ignore[union-attr]
                    return f
            except Exception:
                pass

        video_path = Path(data_dir) / video_id / "frames" / f"{video_id}.mp4"
        if not video_path.exists():
            video_path = Path(data_dir) / video_id / f"{video_id}.mp4"
        if not video_path.exists():
            for p in Path(data_dir).rglob(f"{video_id}*.mp4"):
                video_path = p
                break

        if not video_path.exists():
            raise RuntimeError(f"Video file not found for {video_id} in {data_dir}")

        logger.info("Uploading video %s to Gemini Files API (%s, %.1f MB)...",
                     video_id, video_path.name, video_path.stat().st_size / 1e6)

        uploaded = self.client.files.upload(file=str(video_path))

        import time as _time
        while uploaded.state and uploaded.state.name == "PROCESSING":  # type: ignore[union-attr]
            logger.info("Gemini processing video... (state=%s)", uploaded.state.name)  # type: ignore[union-attr]
            _time.sleep(2)
            uploaded = self.client.files.get(name=uploaded.name or "")

        if not uploaded.state or uploaded.state.name != "ACTIVE":  # type: ignore[union-attr]
            raise RuntimeError(f"Video upload failed: state={uploaded.state}")  # type: ignore[union-attr]

        logger.info("Video uploaded and ready: %s (uri=%s)", uploaded.display_name, uploaded.uri)
        self._uploaded_videos[video_id] = uploaded
        return uploaded

    def generate_answer(
        self,
        retrieval_result: RetrievalResult,
        max_new_tokens: int = 4096,
        temperature: float = 0.3,
        timestamp: float | None = None,
        video_data_dir: str = "./data",
    ) -> AnswerResult:
        # Upload video if needed
        video_file = self._ensure_video_uploaded(
            retrieval_result.video_id, video_data_dir
        )

        # Build transcript context from RAG
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

        # Build prompt
        ts_str = ""
        if timestamp is not None:
            ts_str = f" at timestamp {int(timestamp//60)}:{int(timestamp%60):02d}"

        prompt = (
            f"I have uploaded a lecture video. The student is asking about what happens{ts_str}.\n\n"
            f"Student question: {retrieval_result.query}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Go to the exact timestamp{ts_str} in the video\n"
            f"2. Look at what is on screen — board, slides, diagrams, equations\n"
            f"3. Listen to what the professor is saying at that moment\n"
            f"4. Describe EXACTLY what you see and hear\n"
            f"5. Then explain it clearly for a student\n"
            f"6. Be specific — cite exact numbers, text, and equations visible on screen\n\n"
            f"For reference, here is the transcript around that timestamp:\n\n"
            f"{context_text}"
        )

        t0 = time.perf_counter()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[video_file, prompt],  # type: ignore[list-item]
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
            model_name=f"gemini-video/{self.model_name}",
            generation_time_seconds=round(elapsed, 2),
        )
