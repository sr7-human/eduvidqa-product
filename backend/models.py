"""Request/response Pydantic models for the EduVidQA API layer."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

_YOUTUBE_URL_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


# ── Requests ─────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    youtube_url: str = Field(..., max_length=200, description="Full YouTube URL")
    timestamp: float = Field(..., ge=0, le=360000, description="Position in seconds (max 100 hours)")
    question: str = Field(..., min_length=1, max_length=2048, description="Student's question")
    scope: str = Field(
        default="point",
        pattern="^(point|range|all)$",
        description="'point' = one timestamp; 'range' = a [start, end) interval; 'all' = search the whole lecture",
    )
    start_timestamp: float | None = Field(
        default=None, ge=0, le=360000, description="Range start (seconds), required when scope='range'",
    )
    end_timestamp: float | None = Field(
        default=None, ge=0, le=360000, description="Range end (seconds), required when scope='range'",
    )
    skip_quality_eval: bool = Field(
        default=False, description="Skip quality scoring to save time"
    )
    image_b64: str | None = Field(
        default=None, max_length=12_000_000,
        description="Optional user-pasted screenshot (data URL or base64 JPEG/PNG) used as the visual frame instead of a live YouTube download",
    )

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not _YOUTUBE_URL_PATTERN.search(v):
            raise ValueError("Invalid YouTube URL")
        return v

    @model_validator(mode="after")
    def _validate_range(self) -> "AskRequest":
        if self.scope == "range":
            if self.start_timestamp is None or self.end_timestamp is None:
                raise ValueError("range scope requires start_timestamp and end_timestamp")
            if self.end_timestamp <= self.start_timestamp:
                raise ValueError("start_timestamp must be before end_timestamp")
            if self.end_timestamp - self.start_timestamp > 1800:
                raise ValueError("range must be 30 minutes or less")
        return self


class ProcessRequest(BaseModel):
    youtube_url: str = Field(..., max_length=200, description="Full YouTube URL to pre-process")
    mode: str = Field(
        default="lecture",
        description="Ingest depth: 'lecture' (video + keyframes + vision) or "
        "'podcast' (transcript-only, no video download / keyframes)",
    )
    video_type: str = Field(
        default="auto",
        description="Keyframe quality preset: 'auto' (720p), 'handheld' (1080p), "
        "'slides' (480p) or 'animation' (360p). Ignored in podcast mode.",
    )

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not _YOUTUBE_URL_PATTERN.search(v):
            raise ValueError("Invalid YouTube URL")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = (v or "lecture").strip().lower()
        if v not in {"lecture", "podcast"}:
            raise ValueError("mode must be 'lecture' or 'podcast'")
        return v

    @field_validator("video_type")
    @classmethod
    def validate_video_type(cls, v: str) -> str:
        v = (v or "auto").strip().lower()
        if v not in {"auto", "handheld", "slides", "animation"}:
            raise ValueError("video_type must be auto, handheld, slides or animation")
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
    end_ts: float = Field(..., ge=0, le=360000, description="Timestamp up to which to quiz")
    count: int = Field(default=10, ge=1, le=15, description="Number of questions per checkpoint")


class AttemptRequest(BaseModel):
    selected_answer: str = Field(
        ..., max_length=1, pattern=r"^[A-D]$", description="Selected option A-D"
    )
