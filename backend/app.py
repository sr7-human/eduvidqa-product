"""EduVidQA FastAPI application — orchestrates Ingest → RAG → Inference."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.models import (
    AskRequest,
    AskResponse,
    HealthResponse,
    ProcessRequest,
    ProcessResponse,
    QualityScoresResponse,
    SourceInfo,
)
from pipeline.ingest import ingest_video, parse_video_id
from pipeline.rag import LectureIndex

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Global singletons (initialised in lifespan)
# ---------------------------------------------------------------------------

_index: LectureIndex | None = None
_engine = None  # QwenInference — lazy to avoid import cost at module level


def _get_index() -> LectureIndex:
    global _index
    if _index is None:
        _index = LectureIndex(persist_dir=settings.CHROMA_DIR)
    return _index


def _get_engine():
    """Return (and lazily create) the QwenInference engine."""
    global _engine
    if _engine is None:
        from pipeline.inference import QwenInference

        _engine = QwenInference(
            model_name=settings.MODEL_NAME,
            quantize_4bit=settings.QUANTIZE_4BIT,
        )
    return _engine


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("EduVidQA API starting up …")
    # Always init the vector index (lightweight)
    _get_index()
    # Eagerly load the LLM unless LAZY_LOAD is set
    if not settings.LAZY_LOAD:
        logger.info("Pre-loading inference model (set LAZY_LOAD=true to defer) …")
        _get_engine()
    yield
    # Shutdown — free GPU memory
    global _engine
    if _engine is not None:
        _engine.unload()
        _engine = None
    logger.info("EduVidQA API shut down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EduVidQA API",
    version="1.0.0",
    description="AI Teaching Assistant for YouTube Lectures (EMNLP 2025)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return system status: model loaded, GPU available, etc."""
    return HealthResponse(
        status="ok",
        model_loaded=_engine is not None,
        model_name=settings.MODEL_NAME,
        gpu_available=torch.cuda.is_available(),
    )


@app.post("/api/process-video", response_model=ProcessResponse)
async def process_video(request: ProcessRequest) -> ProcessResponse:
    """Download, transcribe, chunk, and index a video ahead of time."""
    # Validate URL early
    try:
        video_id = parse_video_id(request.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    index = _get_index()

    # Skip if already indexed
    if index.is_indexed(video_id):
        return ProcessResponse(
            video_id=video_id,
            title="(cached)",
            duration=0,
            segment_count=0,
            message="Video already indexed.",
        )

    try:
        result = await ingest_video(request.youtube_url, output_dir=settings.DATA_DIR)
    except RuntimeError as exc:
        detail = str(exc)
        if "private" in detail.lower() or "age" in detail.lower():
            raise HTTPException(status_code=403, detail=detail)
        raise HTTPException(status_code=400, detail=detail)

    seg_count = index.index_segments(result.segments)

    return ProcessResponse(
        video_id=result.metadata.video_id,
        title=result.metadata.title,
        duration=result.metadata.duration,
        segment_count=seg_count,
        message="Video processed and indexed successfully.",
    )


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    """Full pipeline: URL + question → AI answer."""
    # 1. Parse video ID
    try:
        video_id = parse_video_id(request.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    index = _get_index()

    # 2. Ingest if not already indexed
    if not index.is_indexed(video_id):
        try:
            result = await ingest_video(request.youtube_url, output_dir=settings.DATA_DIR)
        except RuntimeError as exc:
            detail = str(exc)
            if "private" in detail.lower() or "age" in detail.lower():
                raise HTTPException(status_code=403, detail=detail)
            raise HTTPException(status_code=400, detail=detail)
        index.index_segments(result.segments)

    # 3. Retrieve relevant segments
    try:
        retrieval = index.retrieve(request.question, video_id, top_k=5)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 4. Generate answer
    engine = _get_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Retry shortly.")

    t0 = time.perf_counter()
    answer_result = engine.generate_answer(retrieval)
    elapsed = time.perf_counter() - t0

    # 5. Build response
    sources = [
        SourceInfo(
            start_time=s["start_time"],
            end_time=s["end_time"],
            relevance_score=s["relevance_score"],
        )
        for s in answer_result.sources
    ]

    quality = None
    if not request.skip_quality_eval and answer_result.quality_scores is not None:
        quality = QualityScoresResponse(
            clarity=answer_result.quality_scores.clarity,
            ect=answer_result.quality_scores.ect,
            upt=answer_result.quality_scores.upt,
        )

    return AskResponse(
        question=answer_result.question,
        answer=answer_result.answer,
        video_id=answer_result.video_id,
        sources=sources,
        quality_scores=quality,
        model_name=answer_result.model_name,
        generation_time_seconds=round(elapsed, 2),
    )
