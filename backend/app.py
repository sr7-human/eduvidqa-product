"""EduVidQA FastAPI application — orchestrates Ingest → RAG → Answer → Score."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure .env is loaded before any other imports read env vars
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path, override=True)
except Exception:
    pass

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
from pipeline.ingest import parse_video_id

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# ---------------------------------------------------------------------------
# Global singletons (initialised lazily)
# ---------------------------------------------------------------------------

_index = None  # LectureIndex from rag_v2


def _get_index():
    from pipeline.rag_v2 import LectureIndex

    global _index
    if _index is None:
        _index = LectureIndex(persist_dir=settings.CHROMA_DIR)
    return _index


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("EduVidQA API starting up …")
    if not settings.LAZY_LOAD:
        logger.info("Pre-loading index (set LAZY_LOAD=true to defer) …")
        _get_index()
    yield
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
    """Return system status."""
    indexed_count = 0
    try:
        idx = _get_index()
        indexed_count = idx._col.count()
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        model_loaded=True,  # using API-based LLMs, always "loaded"
        model_name="groq/llama-4-scout-17b",
        gpu_available=False,
    )


@app.post("/api/process-video", response_model=ProcessResponse)
async def process_video(request: ProcessRequest) -> ProcessResponse:
    """Download, extract keyframes, chunk transcript, generate digest, and index."""
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

    data_dir = settings.DATA_DIR
    processed_dir = os.path.join(data_dir, "processed")

    try:
        # Step 1: Download video
        video_path = _download_video(video_id, data_dir)

        # Step 2: Extract keyframes (Session A)
        from pipeline.keyframes import extract_keyframes

        kf_manifest = extract_keyframes(
            video_path=video_path,
            video_id=video_id,
            output_dir=processed_dir,
        )

        # Step 3: Chunk transcript (Session A)
        from pipeline.chunking import chunk_transcript

        chunks = chunk_transcript(
            video_id=video_id,
            output_dir=processed_dir,
            keyframe_manifest=kf_manifest,
        )

        # Step 4: Generate digest (Session B) — non-fatal if API rate-limited
        digest = ""
        try:
            from pipeline.digest import generate_digest

            digest = generate_digest(video_id=video_id, data_dir=processed_dir)
        except Exception as exc:
            logger.warning("Digest generation failed (non-fatal, indexing without digest): %s", exc)
            # Check if a cached digest.txt exists from a previous partial run
            digest_path = Path(processed_dir) / video_id / "digest.txt"
            if digest_path.exists():
                digest = digest_path.read_text()
                logger.info("Using cached digest from previous run")

        # Step 5: Index in ChromaDB (Session B)
        total = index.index_video(
            video_id=video_id,
            chunks=chunks,
            keyframe_manifest=kf_manifest,
            digest=digest,
        )

        # Step 6: Delete .mp4 to save disk
        try:
            vid_dir = Path(data_dir) / "videos" / video_id
            if vid_dir.is_dir():
                shutil.rmtree(vid_dir)
        except Exception as exc:
            logger.warning("Failed to clean up video dir: %s", exc)

        return ProcessResponse(
            video_id=video_id,
            title=f"Video {video_id}",
            duration=chunks[-1]["end_time"] if chunks else 0,
            segment_count=total,
            message="Video processed and indexed successfully.",
        )

    except Exception as exc:
        logger.error("Processing failed: %s", exc, exc_info=True)
        detail = str(exc)
        if "private" in detail.lower() or "age" in detail.lower():
            raise HTTPException(status_code=403, detail=detail)
        raise HTTPException(status_code=500, detail=detail)


def _download_video(video_id: str, data_dir: str) -> str:
    """Download video .mp4. Tries yt-dlp first, falls back to pytubefix."""
    vid_dir = Path(data_dir) / "videos" / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = vid_dir / f"{video_id}.mp4"

    if mp4_path.exists():
        return str(mp4_path)

    url = f"https://www.youtube.com/watch?v={video_id}"

    # --- Attempt 1: yt-dlp ---
    try:
        import yt_dlp

        ydl_opts = {
            "format": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
            "outtmpl": str(mp4_path),
            "no_playlist": True,
            "merge_output_format": "mp4",
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if mp4_path.exists():
            return str(mp4_path)
    except Exception as exc:
        logger.warning("yt-dlp download failed (%s), trying pytubefix …", exc)

    # --- Attempt 2: pytubefix ---
    try:
        from pytubefix import YouTube

        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").first()
        if stream is None:
            stream = yt.streams.filter(file_extension="mp4").first()
        if stream is None:
            raise RuntimeError("No suitable mp4 stream found")
        stream.download(output_path=str(vid_dir), filename=f"{video_id}.mp4")
        if mp4_path.exists():
            return str(mp4_path)
    except Exception as exc:
        logger.error("pytubefix download also failed: %s", exc)

    raise RuntimeError(f"Could not download video {video_id} — both yt-dlp and pytubefix failed")


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    """Full pipeline: URL + question + timestamp → AI answer."""
    # 1. Parse video ID
    try:
        video_id = parse_video_id(request.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    index = _get_index()

    # 2. Auto-ingest if not indexed
    if not index.is_indexed(video_id):
        try:
            await process_video(ProcessRequest(youtube_url=request.youtube_url))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Auto-ingest failed: {exc}")

    t0 = time.perf_counter()

    # 3. Extract live frame at exact timestamp
    from pipeline.live_frame import extract_live_frame

    live_frame = extract_live_frame(
        video_id=video_id,
        timestamp=request.timestamp,
        data_dir=os.path.join(settings.DATA_DIR, "processed"),
    )

    # 4. Retrieve relevant chunks + keyframes + digest
    retrieval = index.retrieve(
        question=request.question,
        video_id=video_id,
        timestamp=request.timestamp,
        top_k=10,
    )

    # 5. Generate answer
    from pipeline.answer import generate_answer

    try:
        result = generate_answer(
            question=request.question,
            video_id=video_id,
            timestamp=request.timestamp,
            retrieval_result=retrieval,
            live_frame_path=live_frame,
            groq_api_key=settings.GROQ_API_KEY,
            gemini_api_key=settings.GEMINI_API_KEY,
        )
    except Exception as exc:
        logger.error("Answer generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Answer generation failed: {exc}")

    elapsed = time.perf_counter() - t0

    # 6. Quality scoring (optional)
    quality = None
    if not request.skip_quality_eval:
        try:
            from pipeline.evaluate_v2 import score_answer

            scores = score_answer(
                request.question, result["answer"],
                groq_api_key=settings.GROQ_API_KEY,
            )
            quality = QualityScoresResponse(
                clarity=scores["clarity"],
                ect=scores["ect"],
                upt=scores["upt"],
            )
        except Exception as exc:
            logger.warning("Quality scoring failed (non-fatal): %s", exc)

    # 7. Build response
    sources = [
        SourceInfo(
            start_time=s["start_time"],
            end_time=s["end_time"],
            relevance_score=s["relevance_score"],
        )
        for s in result.get("sources", [])
    ]

    return AskResponse(
        question=request.question,
        answer=result["answer"],
        video_id=video_id,
        sources=sources,
        quality_scores=quality,
        model_name=result.get("model_name", "unknown"),
        generation_time_seconds=round(elapsed, 2),
    )
