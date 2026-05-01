"""EduVidQA FastAPI application — orchestrates Ingest → RAG → Answer → Score."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure .env is loaded before any other imports read env vars
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path, override=True)
except Exception:
    pass

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import psycopg2
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.auth import optional_auth, require_auth
from backend.config import settings
from backend.logging_config import request_id_var, setup_logging
from backend.models import (
    AskRequest,
    AskResponse,
    AttemptRequest,
    HealthResponse,
    ProcessRequest,
    ProcessResponse,
    QualityScoresResponse,
    QuizRequest,
    SourceInfo,
)
from pipeline.ingest import parse_video_id

DEMO_VIDEO_ID = "3OmfTIf-SOU"
setup_logging()
logger = logging.getLogger(__name__)

# Sentry: opt-in via SENTRY_DSN env var
if os.getenv("SENTRY_DSN"):
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.1)
        logger.info("Sentry initialised")
    except Exception as exc:  # pragma: no cover
        logger.warning("Sentry init failed: %s", exc)

# ---------------------------------------------------------------------------
# Global singletons (initialised lazily)
# ---------------------------------------------------------------------------

_index = None  # LectureIndex from pipeline.rag


def _get_index():
    from pipeline.rag import LectureIndex

    global _index
    if _index is None:
        _index = LectureIndex()
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
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# DB helpers (Supabase Postgres via psycopg2)
# ---------------------------------------------------------------------------

def _get_db_url() -> str:
    from backend.supabase_config import get_database_url
    return get_database_url()


def _register_video(video_id: str) -> None:
    """Insert pending video row. Idempotent."""
    import uuid
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO videos (id, video_id, pipeline_version, status)
                VALUES (%s, %s, 1, 'pending')
                ON CONFLICT (video_id, pipeline_version) DO NOTHING
                """,
                (str(uuid.uuid4()), video_id),
            )
        conn.commit()
    finally:
        conn.close()


def _get_video_status(video_id: str) -> str | None:
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE video_id = %s", (video_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _update_video_status(video_id: str, status: str, detail: str | None = None) -> None:
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE videos SET status = %s, status_detail = %s, updated_at = now()
                WHERE video_id = %s
                """,
                (status, detail, video_id),
            )
        conn.commit()
    finally:
        conn.close()


def _link_user_video(user_id: str | None, video_id: str) -> None:
    """Track that this user has used this video. No-op if user_id falsy."""
    if not user_id:
        return
    import uuid
    try:
        conn = psycopg2.connect(_get_db_url())
    except Exception as exc:
        logger.warning("_link_user_video DB connect failed (non-fatal): %s", exc)
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_videos (id, user_id, video_id, last_watched_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (user_id, video_id)
                DO UPDATE SET last_watched_at = now(), deleted_at = NULL
                """,
                (str(uuid.uuid4()), user_id, video_id),
            )
        conn.commit()
    except Exception as exc:
        logger.warning("_link_user_video failed (non-fatal): %s", exc)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return system status."""
    return HealthResponse(
        status="ok",
        model_loaded=True,  # using API-based LLMs, always "loaded"
        model_name="groq/llama-4-scout-17b",
        gpu_available=False,
    )


@app.post("/api/process-video")
@limiter.limit("5/minute")
async def process_video(
    request: Request,
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_auth),
):
    """Queue video ingest in background. Returns immediately."""
    try:
        video_id = parse_video_id(body.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    index = _get_index()

    # Already indexed?
    if index.is_indexed(video_id):
        _link_user_video(user_id, video_id)
        # Make sure DB row reflects ready state for status polling
        if _get_video_status(video_id) is None:
            _register_video(video_id)
            _update_video_status(video_id, "ready")
        elif _get_video_status(video_id) != "ready":
            _update_video_status(video_id, "ready")
        return {"video_id": video_id, "status": "ready", "message": "Already indexed"}

    # Already processing?
    status = _get_video_status(video_id)
    if status == "processing":
        return {"video_id": video_id, "status": "processing", "message": "Already being processed"}

    # Register + queue background work
    _register_video(video_id)
    background_tasks.add_task(_ingest_video_bg, video_id, body.youtube_url, user_id)
    return {"video_id": video_id, "status": "processing", "message": "Processing started"}


def _ingest_video_bg(video_id: str, youtube_url: str, user_id: str) -> None:
    """Background ingest — runs in a thread via FastAPI BackgroundTasks."""
    try:
        _update_video_status(video_id, "processing")

        index = _get_index()
        data_dir = settings.DATA_DIR
        processed_dir = os.path.join(data_dir, "processed")

        # Step 1: Download video (non-fatal — cloud IPs often blocked by YouTube)
        video_path = None
        try:
            video_path = _download_video(video_id, data_dir)
        except Exception as exc:
            logger.warning(
                "Video download failed for %s (will proceed transcript-only): %s",
                video_id, exc,
            )

        # Step 2: Extract keyframes (non-fatal — requires .mp4)
        from pipeline.keyframes import extract_keyframes

        kf_manifest: list[dict] = []
        if video_path:
            try:
                kf_manifest = extract_keyframes(
                    video_path=video_path,
                    video_id=video_id,
                    output_dir=processed_dir,
                )
            except Exception as exc:
                logger.warning("Keyframe extraction failed (non-fatal): %s", exc)

        # Step 3: Chunk transcript (always runs — uses youtube-transcript-api)
        from pipeline.chunking import chunk_transcript

        chunks = chunk_transcript(
            video_id=video_id,
            output_dir=processed_dir,
            keyframe_manifest=kf_manifest,
        )

        # Step 4: Generate digest (non-fatal)
        digest = ""
        try:
            from pipeline.digest import generate_digest

            digest = generate_digest(video_id=video_id, data_dir=processed_dir)
        except Exception as exc:
            logger.warning("Digest generation failed (non-fatal): %s", exc)
            digest_path = Path(processed_dir) / video_id / "digest.txt"
            if digest_path.exists():
                digest = digest_path.read_text()

        # Step 5: Index in pgvector
        index.index_video(
            video_id=video_id,
            chunks=chunks,
            keyframe_manifest=kf_manifest,
            digest=digest,
        )

        # Step 6: Place checkpoints (non-fatal)
        checkpoints: list[dict] = []
        try:
            from pipeline.checkpoints import place_checkpoints

            video_duration = chunks[-1].get("end_time", 0) if chunks else 0
            checkpoints = place_checkpoints(chunks, video_duration)

            with psycopg2.connect(_get_db_url()) as cp_conn:
                with cp_conn.cursor() as cp_cur:
                    for cp in checkpoints:
                        cp_cur.execute(
                            """
                            INSERT INTO checkpoints (id, video_id, timestamp_seconds, topic_label)
                            VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                            """,
                            (str(uuid.uuid4()), video_id, cp["timestamp_seconds"], cp["topic_label"]),
                        )
                cp_conn.commit()
            logger.info("Placed %d checkpoints for %s", len(checkpoints), video_id)
        except Exception as exc:
            logger.warning("Checkpoint placement failed (non-fatal): %s", exc)

        # Step 7: Pre-generate quiz for each checkpoint (non-fatal)
        try:
            from pipeline.quiz_cache import get_or_generate

            for cp in checkpoints:
                try:
                    get_or_generate(video_id, cp["timestamp_seconds"], chunks)
                except Exception as exc:
                    logger.warning(
                        "Quiz pre-gen at %.0fs failed: %s", cp["timestamp_seconds"], exc
                    )
        except Exception as exc:
            logger.warning("Quiz pre-gen failed (non-fatal): %s", exc)

        # Step 8: Delete .mp4
        try:
            vid_dir = Path(data_dir) / "videos" / video_id
            if vid_dir.is_dir():
                shutil.rmtree(vid_dir)
        except Exception as exc:
            logger.warning("Failed to clean up video dir: %s", exc)

        _update_video_status(video_id, "ready")
        _link_user_video(user_id, video_id)
    except Exception as exc:
        logger.exception("Ingest failed for %s", video_id)
        try:
            _update_video_status(video_id, "failed", str(exc)[:500])
        except Exception:
            pass


def _download_video(video_id: str, data_dir: str) -> str:
    """Download video .mp4. Tries yt-dlp first, falls back to pytubefix."""
    vid_dir = Path(data_dir) / "videos" / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = vid_dir / f"{video_id}.mp4"

    if mp4_path.exists():
        return str(mp4_path)

    url = f"https://www.youtube.com/watch?v={video_id}"

    # --- Attempt 1: yt-dlp with browser impersonation (bypasses cloud IP blocks) ---
    try:
        import yt_dlp

        ydl_opts = {
            "format": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
            "outtmpl": str(mp4_path),
            "no_playlist": True,
            "merge_output_format": "mp4",
            "quiet": True,
            # Impersonate a real browser to bypass YouTube's bot detection on cloud IPs
            "impersonate": "chrome",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            },
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
@limiter.limit("30/minute")
async def ask_question(
    request: Request,
    body: AskRequest,
    user_id: str | None = Depends(optional_auth),
) -> AskResponse:
    """Full pipeline: URL + question + timestamp → AI answer."""
    # BYOK: Gemini key from request header, fallback to server .env
    user_gemini_key = request.headers.get("X-Gemini-Key", "").strip()
    gemini_key = user_gemini_key or settings.GEMINI_API_KEY

    # 1. Parse video ID
    try:
        video_id = parse_video_id(body.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Unauthenticated → only demo video allowed
    if user_id is None and video_id != DEMO_VIDEO_ID:
        raise HTTPException(status_code=401, detail="Sign in to ask questions on this video")

    # Track user-video link (best effort)
    if user_id:
        _link_user_video(user_id, video_id)

    index = _get_index()

    # 2. Auto-ingest if not indexed — return 202 and queue background work
    if not index.is_indexed(video_id):
        status = _get_video_status(video_id)
        if status == "processing":
            raise HTTPException(status_code=202, detail="Video is still being processed. Try again shortly.")
        if status == "failed":
            raise HTTPException(status_code=422, detail="Video processing failed. Try resubmitting.")
        # Not known — register and queue in a thread
        _register_video(video_id)
        import threading

        t = threading.Thread(
            target=_ingest_video_bg,
            args=(video_id, body.youtube_url, user_id or ""),
            daemon=True,
        )
        t.start()
        raise HTTPException(status_code=202, detail="Video is being processed. Try again in a minute.")

    t0 = time.perf_counter()

    # 3. Extract live frame at exact timestamp (non-fatal)
    from pipeline.live_frame import extract_live_frame

    live_frame = None
    try:
        live_frame = extract_live_frame(
            video_id=video_id,
            timestamp=body.timestamp,
            data_dir=os.path.join(settings.DATA_DIR, "processed"),
        )
    except Exception as exc:
        logger.warning("live_frame extraction failed (non-fatal): %s", exc)

    # 4. Retrieve relevant chunks + keyframes + digest
    retrieval: dict = {"ranked_chunks": [], "relevant_keyframes": [], "digest": ""}
    try:
        retrieval = index.retrieve(
            question=body.question,
            video_id=video_id,
            timestamp=body.timestamp,
            top_k=10,
        )
    except Exception as exc:
        logger.error("Retrieval failed for %s — answering without context: %s", video_id, exc)

    # 5. Generate answer
    from pipeline.answer import generate_answer

    try:
        result = generate_answer(
            question=body.question,
            video_id=video_id,
            timestamp=body.timestamp,
            retrieval_result=retrieval,
            live_frame_path=live_frame,
            groq_api_key=settings.GROQ_API_KEY,
            gemini_api_key=gemini_key,
        )
    except Exception:
        logger.exception("Answer generation failed for %s", video_id)
        raise HTTPException(status_code=500, detail="Internal server error. Please try again.")

    elapsed = time.perf_counter() - t0

    # 6. Quality scoring (optional)
    quality = None
    if not body.skip_quality_eval:
        try:
            from pipeline.evaluate import score_answer

            scores = score_answer(
                body.question, result["answer"],
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
        question=body.question,
        answer=result["answer"],
        video_id=video_id,
        sources=sources,
        quality_scores=quality,
        model_name=result.get("model_name", "unknown"),
        generation_time_seconds=round(elapsed, 2),
    )


@app.get("/api/videos/{video_id}/status")
async def video_status(video_id: str):
    """Frontend polls this while video is processing."""
    status = _get_video_status(video_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"video_id": video_id, "status": status}


@app.get("/api/users/me/videos")
async def my_videos(user_id: str = Depends(require_auth)):
    """Returns list of videos this user has added/watched."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT v.video_id, v.title, v.duration_seconds, v.status,
                       uv.last_watched_at, uv.last_position_seconds
                FROM user_videos uv
                JOIN videos v ON uv.video_id = v.video_id
                WHERE uv.user_id = %s AND uv.deleted_at IS NULL
                ORDER BY uv.last_watched_at DESC NULLS LAST
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "video_id": r[0],
            "title": r[1],
            "duration": r[2],
            "status": r[3],
            "last_watched_at": str(r[4]) if r[4] else None,
            "last_position": r[5],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Quiz / Checkpoints / Spaced Repetition
# ---------------------------------------------------------------------------


@app.get("/api/videos/{video_id}/checkpoints")
async def get_checkpoints(video_id: str, user_id: str = Depends(require_auth)):
    """Return ordered checkpoints for a video."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, timestamp_seconds, topic_label
                FROM checkpoints WHERE video_id = %s
                ORDER BY timestamp_seconds
                """,
                (video_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"id": str(r[0]), "timestamp_seconds": r[1], "topic_label": r[2]} for r in rows
    ]


@app.post("/api/videos/{video_id}/quiz")
async def get_quiz(
    video_id: str, body: QuizRequest, user_id: str = Depends(require_auth)
):
    """Return quiz questions for a checkpoint timestamp (answers/explanations stripped)."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT chunk_id, text, start_time, end_time FROM video_chunks WHERE video_id = %s",
                (video_id,),
            )
            chunks = [
                {"chunk_id": r[0], "text": r[1], "start_time": r[2], "end_time": r[3]}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()
    if not chunks:
        raise HTTPException(status_code=404, detail="Video not indexed")

    from pipeline.quiz_cache import get_or_generate

    questions = get_or_generate(video_id, body.end_ts, chunks)

    return {
        "questions": [
            {
                "id": q["id"],
                "question_text": q["question_text"],
                "options": q["options"],
                "difficulty": q.get("difficulty", "medium"),
            }
            for q in questions[: body.count]
        ]
    }


@app.post("/api/quizzes/{question_id}/attempt")
async def submit_attempt(
    question_id: str, body: AttemptRequest, user_id: str = Depends(require_auth)
):
    """Record a quiz attempt; on wrong answer, schedule review for tomorrow."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT correct_answer, explanation FROM questions WHERE id = %s",
                (question_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Question not found")

            correct_answer, explanation = row
            is_correct = body.selected_answer == correct_answer

            cur.execute(
                """
                INSERT INTO quiz_attempts (id, user_id, question_id, selected_answer, is_correct)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_id, question_id, body.selected_answer, is_correct),
            )

            added_to_review = False
            if not is_correct:
                cur.execute(
                    """
                    INSERT INTO review_queue (id, user_id, question_id, next_review_at)
                    VALUES (%s, %s, %s, now() + interval '1 day')
                    ON CONFLICT (user_id, question_id) DO UPDATE SET
                        next_review_at = now() + interval '1 day',
                        interval_days = 1, repetitions = 0
                    """,
                    (str(uuid.uuid4()), user_id, question_id),
                )
                added_to_review = True

        conn.commit()
    finally:
        conn.close()
    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "added_to_review": added_to_review,
    }


@app.get("/api/users/me/review")
async def get_review(user_id: str = Depends(require_auth)):
    """Return up to 20 due review items for the current user."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT q.id, q.video_id, v.title, q.question_text, q.options, rq.next_review_at
                FROM review_queue rq
                JOIN questions q ON rq.question_id = q.id
                LEFT JOIN videos v ON q.video_id = v.video_id
                WHERE rq.user_id = %s AND rq.next_review_at <= now()
                ORDER BY rq.next_review_at LIMIT 20
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "due_count": len(rows),
        "questions": [
            {
                "id": str(r[0]),
                "video_id": r[1],
                "video_title": r[2],
                "question_text": r[3],
                "options": r[4],
                "next_review_at": str(r[5]),
            }
            for r in rows
        ],
    }


@app.post("/api/review/{question_id}/attempt")
async def review_attempt(
    question_id: str, body: AttemptRequest, user_id: str = Depends(require_auth)
):
    """Record a review attempt and update SM-2 schedule."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT correct_answer, explanation FROM questions WHERE id = %s",
                (question_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Question not found")

            correct_answer, explanation = row
            is_correct = body.selected_answer == correct_answer

            cur.execute(
                """
                SELECT repetitions, ease_factor, interval_days FROM review_queue
                WHERE user_id = %s AND question_id = %s
                """,
                (user_id, question_id),
            )
            rq = cur.fetchone()
            if rq:
                from pipeline.spaced_repetition import sm2_update

                new_reps, new_ef, new_iv = sm2_update(is_correct, rq[0], rq[1], rq[2])
                cur.execute(
                    """
                    UPDATE review_queue SET repetitions = %s, ease_factor = %s,
                        interval_days = %s, next_review_at = now() + make_interval(days => %s)
                    WHERE user_id = %s AND question_id = %s
                    """,
                    (new_reps, new_ef, new_iv, new_iv, user_id, question_id),
                )

            cur.execute(
                """
                INSERT INTO quiz_attempts (id, user_id, question_id, selected_answer, is_correct)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_id, question_id, body.selected_answer, is_correct),
            )

        conn.commit()
    finally:
        conn.close()
    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }


@app.delete("/api/users/me")
async def delete_my_data(user_id: str = Depends(require_auth)):
    """Delete ALL user-owned data. Does not delete global data (videos, questions)."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM review_queue WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM quiz_attempts WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM user_videos WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()
    logger.info("Deleted all data for user %s", user_id)
    return {"message": "All your data has been deleted."}
