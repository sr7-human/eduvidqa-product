"""Request/response Pydantic models for the EduVidQA API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    youtube_url: str = Field(..., description="Full YouTube URL")
    timestamp: float = Field(..., ge=0, description="Position in seconds")
    question: str = Field(..., min_length=1, description="Student's question")
    skip_quality_eval: bool = Field(
        default=False, description="Skip quality scoring to save time"
    )


class ProcessRequest(BaseModel):
    youtube_url: str = Field(..., description="Full YouTube URL to pre-process")


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
