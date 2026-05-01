"""Request/response Pydantic models for the EduVidQA API layer."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_YOUTUBE_URL_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


# ── Requests ─────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    youtube_url: str = Field(..., max_length=200, description="Full YouTube URL")
    timestamp: float = Field(..., ge=0, le=21600, description="Position in seconds (max 6 hours)")
    question: str = Field(..., min_length=1, max_length=2048, description="Student's question")
    skip_quality_eval: bool = Field(
        default=False, description="Skip quality scoring to save time"
    )

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not _YOUTUBE_URL_PATTERN.search(v):
            raise ValueError("Invalid YouTube URL")
        return v


class ProcessRequest(BaseModel):
    youtube_url: str = Field(..., max_length=200, description="Full YouTube URL to pre-process")

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not _YOUTUBE_URL_PATTERN.search(v):
            raise ValueError("Invalid YouTube URL")
        return v


# ── Responses ────────────────────────────────────────────────────────


class SourceInfo(BaseModel):
    start_time: float
    end_time: float
    relevance_score: float


class QualityScoresResponse(BaseModel):
    clarity: float = Field(..., ge=1, le=5)
    ect: float = Field(..., ge=1, le=5)
    upt: float = Field(..., ge=1, le=5)


class AskResponse(BaseModel):
    question: str
    answer: str
    video_id: str
    sources: list[SourceInfo]
    quality_scores: QualityScoresResponse | None = None
    model_name: str
    generation_time_seconds: float


class ProcessResponse(BaseModel):
    video_id: str
    title: str
    duration: float
    segment_count: int
    message: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str
    gpu_available: bool


# ── Quiz / Review ────────────────────────────────────────────────────


class QuizRequest(BaseModel):
    end_ts: float = Field(..., ge=0, le=21600, description="Timestamp up to which to quiz")
    count: int = Field(default=3, ge=1, le=10, description="Number of questions")


class AttemptRequest(BaseModel):
    selected_answer: str = Field(
        ..., max_length=1, pattern=r"^[A-D]$", description="Selected option A-D"
    )
