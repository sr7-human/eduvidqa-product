"""Shared Pydantic data models used by all pipeline sessions."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VideoSegment(BaseModel):
    """A 2-minute chunk of a lecture video with aligned text + frames."""

    video_id: str  # YouTube video ID (e.g., "dQw4w9WgXcQ")
    segment_index: int  # 0-based index of this chunk
    start_time: float  # Start timestamp in seconds
    end_time: float  # End timestamp in seconds
    transcript_text: str  # Transcript text for this segment
    frame_paths: list[str]  # Paths to extracted key frames (JPEGs)


class VideoMetadata(BaseModel):
    """Metadata about a processed video."""

    video_id: str
    title: str
    duration: float  # Total duration in seconds
    channel: str
    segment_count: int
    transcript_source: str  # "captions" or "whisper"


class IngestResult(BaseModel):
    """Output of the full ingestion pipeline."""

    metadata: VideoMetadata
    segments: list[VideoSegment]


# ── Session B output models ──────────────────────────────────────────


class RetrievedContext(BaseModel):
    """A single retrieved segment with its relevance score."""

    segment: VideoSegment
    relevance_score: float
    rank: int


class RetrievalResult(BaseModel):
    """Output of the retrieval pipeline (Session B)."""

    query: str  # Student's question
    video_id: str
    contexts: list[RetrievedContext]
    total_segments: int


# ── Session C output models ──────────────────────────────────────────


class QualityScores(BaseModel):
    """Likert scale scores (1-5) from the EduVidQA paper."""

    clarity: float = Field(..., ge=1, le=5, description="Is the answer clear and jargon-free?")
    ect: float = Field(..., ge=1, le=5, description="Does it encourage critical thinking?")
    upt: float = Field(..., ge=1, le=5, description="Does it use pedagogical techniques?")


class AnswerResult(BaseModel):
    """Final output: the AI-generated answer with metadata."""

    question: str
    answer: str
    video_id: str
    sources: list[dict]  # [{start_time, end_time, relevance_score}]
    quality_scores: Optional[QualityScores] = None
    model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    generation_time_seconds: float
