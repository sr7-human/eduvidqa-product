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
from fastapi.responses import StreamingResponse

import psycopg2
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.auth import optional_auth, require_admin, require_auth, verify_token, _admin_emails
from pydantic import BaseModel, Field
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
    allow_methods=["GET", "POST", "DELETE", "PUT", "PATCH", "OPTIONS"],
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


def _fetch_video_title(video_id: str) -> str | None:
    """Fetch a YouTube video's title via the free oEmbed endpoint (no API key)."""
    import json as _json
    import urllib.request
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            title = data.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()[:300]
    except Exception as exc:  # noqa: BLE001
        logger.warning("oEmbed title fetch failed for %s: %s", video_id, exc)
    return None


def _set_video_title(video_id: str, title: str) -> None:
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET title = %s, updated_at = now() WHERE video_id = %s",
                (title, video_id),
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


def _get_user_keys(user_id: str | None) -> dict[str, str]:
    """Fetch this user's stored API keys (gemini, groq). Returns {} if none."""
    if not user_id:
        return {}
    try:
        conn = psycopg2.connect(_get_db_url())
    except Exception as exc:
        logger.warning("_get_user_keys connect failed: %s", exc)
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT service, key_value FROM user_api_keys WHERE user_id = %s",
                (user_id,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as exc:
        logger.warning("_get_user_keys query failed: %s", exc)
        return {}
    finally:
        conn.close()


def _get_llm_pref(user_id: str | None) -> str:
    """Return user's LLM preference: 'auto', 'groq', or 'gemini'."""
    if not user_id:
        return "auto"
    try:
        conn = psycopg2.connect(_get_db_url())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT llm_pref FROM user_quiz_prefs WHERE user_id = %s::uuid",
                    (user_id,),
                )
                row = cur.fetchone()
                return row[0] if row else "auto"
        finally:
            conn.close()
    except Exception:
        return "auto"


class _ScopedAPIKeys:
    """Context manager that temporarily injects user-specific GEMINI_API_KEY /
    GROQ_API_KEY into os.environ for the duration of a request, restoring the
    server defaults afterwards.

    Used so that downstream code (pipeline.answer, pipeline.quiz_gen,
    pipeline.embeddings) — which reads keys via ``os.getenv`` — automatically
    picks up the user's key without needing to thread arguments everywhere.
    """

    SERVICE_TO_ENV = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}

    def __init__(self, user_id: str | None, allow_server_fallback: bool = False):
        self.user_id = user_id
        self.allow_server_fallback = allow_server_fallback
        self._saved: dict[str, str | None] = {}

    def __enter__(self):
        keys = _get_user_keys(self.user_id) if self.user_id else {}
        for service, env_name in self.SERVICE_TO_ENV.items():
            self._saved[env_name] = os.environ.get(env_name)
            user_key = keys.get(service)
            if user_key:
                os.environ[env_name] = user_key
            elif not self.allow_server_fallback:
                # User has no key for this service AND we're not allowed to
                # fall back to the server's key — clear it so downstream code
                # treats it as missing.
                os.environ.pop(env_name, None)
            # else: leave server key in place
        return self

    def __exit__(self, exc_type, exc, tb):
        for env_name, prev in self._saved.items():
            if prev is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = prev
        return False


def _user_has_any_key(user_id: str | None) -> bool:
    keys = _get_user_keys(user_id)
    return bool(keys.get("gemini") or keys.get("groq"))


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


@app.get("/api/video-preview")
async def video_preview(youtube_url: str, user_id: str = Depends(require_auth)):
    """Lightweight metadata probe — returns duration, title, estimated chapters.

    Uses yt-dlp in extract-info mode (no download). Fast enough for a preview modal.
    """
    try:
        video_id = parse_video_id(youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "no_color": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False,
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not fetch video metadata: {exc}")

    duration_sec = info.get("duration") or 0
    duration_min = duration_sec / 60
    title = info.get("title") or video_id

    # YouTube chapters if present
    yt_chapters = info.get("chapters") or []
    if yt_chapters:
        chapter_count = len(yt_chapters)
    else:
        chapter_count = max(1, min(8, round(duration_min / 12)))

    return {
        "video_id": video_id,
        "title": title,
        "duration_seconds": duration_sec,
        "estimated_chapters": chapter_count,
        "has_youtube_chapters": len(yt_chapters) > 0,
    }


@app.post("/api/process-video")
@limiter.limit("5/minute")
async def process_video(
    request: Request,
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_auth),
):
    """Queue video ingest in background. Returns immediately.

    If the URL is a playlist, queues ALL videos from that playlist instead.
    """
    # Playlist? -> bulk-queue every video in it
    playlist_id = _extract_playlist_id(body.youtube_url)
    if playlist_id:
        # Playlists never include the demo, so a key is required
        if not _user_has_any_key(user_id):
            raise HTTPException(
                status_code=402,
                detail="Add a Gemini or Groq API key in Settings before processing playlists.",
            )
        try:
            video_ids = _list_playlist_video_ids(playlist_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not read playlist: {exc}")
        if not video_ids:
            raise HTTPException(status_code=400, detail="Playlist has no videos.")

        index = _get_index()
        queued = 0
        already = 0
        for vid in video_ids:
            try:
                if index.is_indexed(vid):
                    _link_user_video(user_id, vid)
                    already += 1
                    continue
                status = _get_video_status(vid)
                if status == "processing":
                    already += 1
                    continue
                _register_video(vid)
                _link_user_video(user_id, vid)
                background_tasks.add_task(
                    _ingest_video_bg, vid, f"https://www.youtube.com/watch?v={vid}", user_id,
                )
                queued += 1
            except Exception as exc:
                logger.warning("Failed to queue %s from playlist: %s", vid, exc)
        return {
            "playlist_id": playlist_id,
            "total_videos": len(video_ids),
            "queued": queued,
            "already_present": already,
            "message": f"Queued {queued} new video(s) from playlist ({already} already in library).",
        }

    # Single-video flow
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

    # BYOK: non-demo videos require the user's own key (we won't burn server quota)
    if video_id != DEMO_VIDEO_ID and not _user_has_any_key(user_id):
        raise HTTPException(
            status_code=402,
            detail="Add a Gemini or Groq API key in Settings before processing videos. Your key is used for embeddings, quizzes and answers — we never store anyone else's keys against your quota.",
        )

    # Register + queue background work
    _register_video(video_id)
    _link_user_video(user_id, video_id)
    background_tasks.add_task(_ingest_video_bg, video_id, body.youtube_url, user_id)
    return {"video_id": video_id, "status": "processing", "message": "Processing started"}


def _extract_playlist_id(url: str) -> str | None:
    """Return the YouTube playlist ID from a URL if present, else None."""
    import re
    if not url:
        return None
    m = re.search(r"[?&]list=([A-Za-z0-9_-]+)", url)
    if m:
        pid = m.group(1)
        # Skip 'mix' / 'radio' playlists which are infinite/auto-generated
        if pid.startswith(("RD", "UL", "OL")):
            return None
        return pid
    return None


def _list_playlist_video_ids(playlist_id: str) -> list[str]:
    """Use yt-dlp in flat-extract mode to enumerate video IDs of a playlist."""
    import yt_dlp
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlist_items": "1-200",  # cap at 200 videos to be safe
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = (info or {}).get("entries") or []
    ids: list[str] = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id") or e.get("video_id")
        if isinstance(vid, str) and len(vid) == 11:
            ids.append(vid)
    # Dedupe while preserving order
    seen: set[str] = set()
    return [v for v in ids if not (v in seen or seen.add(v))]


def _ingest_video_bg(video_id: str, youtube_url: str, user_id: str) -> None:
    """Background ingest — runs in a thread via FastAPI BackgroundTasks.

    Two-phase flow for instant UX:
    PHASE 1 (~10–20s): chunk transcript → embed → mark `transcript_ready`
        User can now open the player and ask transcript-only questions.
    PHASE 2 (background): download video → keyframes → embed → digest →
        checkpoints → quiz pre-gen → mark `ready`.

    Uses the user's API keys (from user_api_keys table) for embeddings + LLM.
    For the demo video, falls back to the server's keys.
    """
    is_demo = (video_id == DEMO_VIDEO_ID)
    with _ScopedAPIKeys(user_id or None, allow_server_fallback=is_demo):
        _ingest_video_bg_inner(video_id, youtube_url, user_id)


def _ingest_video_bg_inner(video_id: str, youtube_url: str, user_id: str) -> None:
    try:
        _update_video_status(video_id, "processing")

        index = _get_index()
        data_dir = settings.DATA_DIR
        processed_dir = os.path.join(data_dir, "processed")

        # Step 0: Fetch + store the YouTube title (cheap oEmbed call)
        try:
            title = _fetch_video_title(video_id)
            if title:
                _set_video_title(video_id, title)
                logger.info("Title for %s: %s", video_id, title)
        except Exception as exc:
            logger.warning("Title fetch failed (non-fatal): %s", exc)

        # ════════════ PHASE 1: Transcript-only (fast) ════════════
        from pipeline.chunking import chunk_transcript

        chunks = chunk_transcript(
            video_id=video_id,
            output_dir=processed_dir,
            keyframe_manifest=[],  # no keyframes yet — link them in phase 2
        )

        if chunks:
            index.index_video(
                video_id=video_id,
                chunks=chunks,
                keyframe_manifest=[],
                digest="",
                manage_status=False,
            )
            _update_video_status(video_id, "transcript_ready")
            _link_user_video(user_id, video_id)
            logger.info(
                "Phase 1 done for %s: %d chunks indexed (transcript_ready)",
                video_id, len(chunks),
            )
        else:
            logger.warning("No transcript available for %s — skipping phase 1", video_id)

        # ════════════ PHASE 2: Video download + keyframes (slow) ════════════

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

        # Step 3: Re-chunk transcript with keyframe links (idempotent via ON CONFLICT)
        if kf_manifest:
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

        # Step 5: Index keyframes + digest (chunks re-inserted as no-op via ON CONFLICT)
        index.index_video(
            video_id=video_id,
            chunks=chunks,
            keyframe_manifest=kf_manifest,
            digest=digest,
            manage_status=False,
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

        # Step 7: Pre-generate quizzes for ALL checkpoints in a SINGLE batched LLM call
        try:
            from pipeline.quiz_gen import generate_quizzes_for_checkpoints
            from pipeline.quiz_cache import (
                cache_questions,
                get_cached_questions,
            )

            # Only generate for checkpoints that don't already have a cached quiz
            todo: list[float] = []
            for cp in checkpoints:
                ts = float(cp["timestamp_seconds"])
                if not get_cached_questions(video_id, int(ts // 30), 1):
                    todo.append(ts)

            if todo:
                logger.info(
                    "Batched quiz pre-gen for %s: %d checkpoint(s) in 1 LLM call",
                    video_id, len(todo),
                )
                results = generate_quizzes_for_checkpoints(video_id, todo, chunks)
                for ts, questions in results.items():
                    if questions:
                        cache_questions(video_id, int(ts // 30), 1, questions)
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

    # --- Attempt 1: yt-dlp with Chrome impersonation (bypasses cloud IP blocks) ---
    try:
        import yt_dlp
        from yt_dlp.networking.impersonate import ImpersonateTarget

        ydl_opts = {
            "format": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
            "outtmpl": str(mp4_path),
            "no_playlist": True,
            "merge_output_format": "mp4",
            "quiet": True,
            "impersonate": ImpersonateTarget("chrome"),
            "extractor_args": {"youtube": {"player_client": ["web", "default"]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if mp4_path.exists():
            return str(mp4_path)
    except Exception as exc:
        logger.warning("yt-dlp impersonate failed (%s), retrying without impersonation …", exc)

    # --- Attempt 1b: yt-dlp without impersonation (fallback) ---
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
        logger.warning("yt-dlp (no impersonate) failed (%s), trying pytubefix …", exc)

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
    # 1. Parse video ID
    try:
        video_id = parse_video_id(body.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Unauthenticated → only demo video allowed
    if user_id is None and video_id != DEMO_VIDEO_ID:
        raise HTTPException(status_code=401, detail="Sign in to ask questions on this video")

    # BYOK: signed-in users on non-demo videos must supply their own key
    is_demo = (video_id == DEMO_VIDEO_ID)
    if user_id and not is_demo and not _user_has_any_key(user_id):
        raise HTTPException(
            status_code=402,
            detail="Add a Gemini or Groq API key in Settings to use your own quota for non-demo videos.",
        )

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

    # 5. Generate answer (using user's keys if present, else server's for demo)
    from pipeline.answer import generate_answer

    try:
        with _ScopedAPIKeys(user_id, allow_server_fallback=is_demo):
            result = generate_answer(
                question=body.question,
                video_id=video_id,
                timestamp=body.timestamp,
                retrieval_result=retrieval,
                live_frame_path=live_frame,
                groq_api_key=os.getenv("GROQ_API_KEY") or None,
                gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
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


@app.post("/api/ask/stream")
@limiter.limit("30/minute")
async def ask_question_stream(
    request: Request,
    body: AskRequest,
    user_id: str | None = Depends(optional_auth),
):
    """Streaming version of /api/ask — emits Server-Sent Events so the UI can
    render the answer token-by-token as the LLM generates it.

    Event format (each preceded by ``data: `` and followed by ``\\n\\n``):
      - ``{"type": "sources", "sources": [...]}`` — emitted first, from retrieval
      - ``{"type": "token",   "text": "..."}``     — one per text chunk
      - ``{"type": "done",    "model_name": "...", "generation_time_seconds": X,
            "quality_scores": {...}|null}``        — final event
      - ``{"type": "error",   "detail": "..."}``   — on failure
    """
    # ── Same gating logic as /api/ask (kept inline to avoid refactor risk) ──
    try:
        video_id = parse_video_id(body.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if user_id is None and video_id != DEMO_VIDEO_ID:
        raise HTTPException(status_code=401, detail="Sign in to ask questions on this video")

    is_demo = (video_id == DEMO_VIDEO_ID)
    if user_id and not is_demo and not _user_has_any_key(user_id):
        raise HTTPException(
            status_code=402,
            detail="Add a Gemini or Groq API key in Settings to use your own quota for non-demo videos.",
        )

    if user_id:
        _link_user_video(user_id, video_id)

    index = _get_index()

    if not index.is_indexed(video_id):
        status = _get_video_status(video_id)
        if status == "processing":
            raise HTTPException(status_code=202, detail="Video is still being processed. Try again shortly.")
        if status == "failed":
            raise HTTPException(status_code=422, detail="Video processing failed. Try resubmitting.")
        _register_video(video_id)
        import threading

        t = threading.Thread(
            target=_ingest_video_bg,
            args=(video_id, body.youtube_url, user_id or ""),
            daemon=True,
        )
        t.start()
        raise HTTPException(status_code=202, detail="Video is being processed. Try again in a minute.")

    # ── Pre-stream: moved retrieval INSIDE event_stream() so the browser
    # receives progress events immediately instead of waiting 20-30s. ──

    # Snapshot user_id / flags for the generator below (closure)
    _user_id = user_id
    _is_demo = is_demo
    _skip_eval = body.skip_quality_eval if body.skip_quality_eval is not None else True
    _question = body.question
    _timestamp = body.timestamp
    _video_id = video_id
    _index = index
    _llm_pref = _get_llm_pref(user_id)  # 'auto' | 'groq' | 'gemini'

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def event_stream():
        from pipeline.answer import generate_answer_stream
        from pipeline.live_frame import extract_live_frame

        # 0) Tell the client we're working — appears instantly
        yield _sse({"type": "status", "text": "Retrieving context…"})

        # 1) Retrieval (embedding + pgvector) — now inside the stream
        live_frame = None
        try:
            live_frame = extract_live_frame(
                video_id=_video_id,
                timestamp=_timestamp,
                data_dir=os.path.join(settings.DATA_DIR, "processed"),
            )
        except Exception as exc:
            logger.warning("live_frame extraction failed (non-fatal): %s", exc)

        retrieval: dict = {"ranked_chunks": [], "relevant_keyframes": [], "digest": ""}
        try:
            retrieval = _index.retrieve(
                question=_question,
                video_id=_video_id,
                timestamp=_timestamp,
                top_k=10,
            )
        except Exception as exc:
            logger.error("Retrieval failed for %s — answering without context: %s", _video_id, exc)

        sources_payload = [
            {
                "start_time": ch.get("start_time", 0),
                "end_time": ch.get("end_time", 0),
                "relevance_score": ch.get("similarity", 0),
            }
            for ch in retrieval.get("ranked_chunks", [])[:10]
        ]

        # 2) Send sources
        yield _sse({"type": "sources", "sources": sources_payload})
        yield _sse({"type": "status", "text": "Generating answer…"})

        full_text_parts: list[str] = []
        model_name = "unknown"
        gen_time = 0.0
        t0 = time.perf_counter()

        try:
            with _ScopedAPIKeys(_user_id, allow_server_fallback=_is_demo):
                # Apply user's LLM preference
                groq_key = os.getenv("GROQ_API_KEY") or None
                gemini_key = os.getenv("GEMINI_API_KEY") or None
                if _llm_pref == "groq":
                    gemini_key = None  # don't fall back to Gemini
                elif _llm_pref == "gemini":
                    groq_key = None    # skip Groq entirely

                for event in generate_answer_stream(
                    question=_question,
                    video_id=_video_id,
                    timestamp=_timestamp,
                    retrieval_result=retrieval,
                    live_frame_path=live_frame,
                    groq_api_key=groq_key,
                    gemini_api_key=gemini_key,
                ):
                    if event.get("type") == "token":
                        full_text_parts.append(event.get("text", ""))
                        yield _sse(event)
                    elif event.get("type") == "end":
                        model_name = event.get("model_name", "unknown")
                        gen_time = event.get("generation_time", 0.0)
        except Exception as exc:
            logger.exception("Streaming answer generation failed for %s", _video_id)
            # If we already sent tokens, don't wipe the partial answer — just
            # append a note and close the stream gracefully.
            if full_text_parts:
                yield _sse({"type": "token", "text": "\n\n*(Answer was cut short due to a server error. You can try asking again.)*"})
            else:
                yield _sse({"type": "error", "detail": "Internal server error. Please try again."})

        # 2) Quality scoring AFTER streaming (so the user has already seen the text)
        full_answer = "".join(full_text_parts).strip()
        quality_payload = None
        if not _skip_eval and full_answer:
            try:
                yield _sse({"type": "status", "text": "Scoring quality…"})
                from pipeline.evaluate import score_answer

                scores = score_answer(
                    _question, full_answer,
                    groq_api_key=settings.GROQ_API_KEY,
                )
                quality_payload = {
                    "clarity": scores["clarity"],
                    "ect": scores["ect"],
                    "upt": scores["upt"],
                }
            except Exception as exc:
                logger.warning("Quality scoring failed (non-fatal): %s", exc)

        elapsed_total = round(time.perf_counter() - t0, 2)
        yield _sse({
            "type": "done",
            "model_name": model_name,
            "generation_time_seconds": gen_time or elapsed_total,
            "quality_scores": quality_payload,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx, etc.)
            "Connection": "keep-alive",
        },
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


@app.get("/api/videos/{video_id}/chapters")
async def get_chapters(video_id: str, user_id: str | None = Depends(optional_auth)):
    """Return ordered chapters for a video (YouTube or synthesized)."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, idx, start_time, end_time, title, source
                FROM chapters
                WHERE video_id = %s
                ORDER BY idx
                """,
                (video_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": str(r[0]),
            "idx": r[1],
            "start_time": float(r[2]),
            "end_time": float(r[3]),
            "title": r[4],
            "source": r[5],
        }
        for r in rows
    ]


def _resolve_blocking_mode(user_id: str | None, video_id: str) -> str:
    """Resolve effective blocking mode: user pref overrides video default."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT quiz_blocking_mode FROM videos WHERE video_id = %s", (video_id,),
            )
            row = cur.fetchone()
            video_default = (row[0] if row else "mandatory") or "mandatory"
            user_pref = "use_video_default"
            if user_id:
                cur.execute(
                    "SELECT pref FROM user_quiz_prefs WHERE user_id = %s::uuid", (user_id,),
                )
                p = cur.fetchone()
                if p and p[0]:
                    user_pref = p[0]
    finally:
        conn.close()
    if user_pref == "always_pause":
        return "mandatory"
    if user_pref == "never_pause":
        return "optional"
    return video_default  # use_video_default


@app.get("/api/videos/{video_id}/quiz-schedule")
async def get_quiz_schedule(
    video_id: str, user_id: str | None = Depends(optional_auth),
):
    """Return ordered quiz events for the player to watch for.

    Each event = ``{timestamp, type, chapter_id, chapter_idx, chapter_title}``.
    Frontend listens to ``onTimeUpdate`` and triggers a quiz modal when it
    crosses any of these timestamps.
    """
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            # Pretests fire at chapter start; end-recalls at chapter end;
            # mid-recalls have their own timestamps stored on the question rows.
            cur.execute(
                """
                SELECT id, idx, start_time, end_time, title
                FROM chapters
                WHERE video_id = %s
                ORDER BY idx
                """,
                (video_id,),
            )
            chapter_rows = cur.fetchall()

            cur.execute(
                """
                SELECT chapter_id, quiz_type, count(*) AS n
                FROM questions
                WHERE video_id = %s AND prompt_version = 2 AND chapter_id IS NOT NULL
                GROUP BY chapter_id, quiz_type
                """,
                (video_id,),
            )
            present: dict[tuple, int] = {(str(r[0]), r[1]): r[2] for r in cur.fetchall()}
    finally:
        conn.close()

    events: list[dict] = []
    for ch_id, idx, start, end, title in chapter_rows:
        ch_id_s = str(ch_id)
        if present.get((ch_id_s, "pretest"), 0) > 0:
            events.append({
                "timestamp": float(start),
                "type": "pretest",
                "chapter_id": ch_id_s,
                "chapter_idx": idx,
                "chapter_title": title,
            })
        if present.get((ch_id_s, "end_recall"), 0) > 0:
            events.append({
                "timestamp": float(end),
                "type": "end_recall",
                "chapter_id": ch_id_s,
                "chapter_idx": idx,
                "chapter_title": title,
            })

    # mid-recalls: each question carries its own ts_bucket; for now, group by
    # bucket and pick the lowest timestamp per bucket as the trigger point.
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT chapter_id, ts_bucket_30s
                FROM questions
                WHERE video_id = %s AND prompt_version = 2
                  AND quiz_type = 'mid_recall' AND chapter_id IS NOT NULL
                """,
                (video_id,),
            )
            for ch_id, bucket in cur.fetchall():
                # find chapter title/idx
                ch_meta = next((r for r in chapter_rows if str(r[0]) == str(ch_id)), None)
                if not ch_meta:
                    continue
                events.append({
                    "timestamp": float(bucket * 30),
                    "type": "mid_recall",
                    "chapter_id": str(ch_id),
                    "chapter_idx": ch_meta[1],
                    "chapter_title": ch_meta[4],
                })
    finally:
        conn.close()

    events.sort(key=lambda e: e["timestamp"])
    blocking_mode = _resolve_blocking_mode(user_id, video_id)
    return {"events": events, "blocking_mode": blocking_mode}


@app.get("/api/videos/{video_id}/chapter-quiz")
async def get_chapter_quiz(
    video_id: str,
    chapter_id: str,
    quiz_type: str = "pretest",
    user_id: str | None = Depends(optional_auth),
):
    """Fetch quiz questions for a (chapter, quiz_type). Returns options + per-option
    explanations. Correct answer + explanations are revealed only AFTER attempt
    submission via the existing /api/quizzes/{question_id}/attempt endpoint.
    """
    if quiz_type not in {"pretest", "mid_recall", "end_recall", "remediation"}:
        raise HTTPException(status_code=400, detail="Invalid quiz_type")
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, question_text, options, difficulty, bloom_level, order_idx
                FROM questions
                WHERE video_id = %s AND chapter_id = %s::uuid
                  AND quiz_type = %s AND prompt_version = 2
                ORDER BY order_idx, question_text
                """,
                (video_id, chapter_id, quiz_type),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "questions": [
            {
                "id": str(r[0]),
                "question_text": r[1],
                "options": r[2] if isinstance(r[2], list) else json.loads(r[2] or "[]"),
                "difficulty": r[3] or "medium",
                "bloom_level": r[4] or "understand",
            }
            for r in rows
        ]
    }


@app.get("/api/users/me/quiz-pref")
async def get_quiz_pref(user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pref FROM user_quiz_prefs WHERE user_id = %s::uuid", (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return {"pref": (row[0] if row else "use_video_default")}


class _QuizPrefBody(BaseModel):
    pref: str = Field(..., pattern=r"^(use_video_default|always_pause|never_pause)$")


@app.put("/api/users/me/quiz-pref")
async def set_quiz_pref(body: _QuizPrefBody, user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_quiz_prefs (user_id, pref, updated_at)
                VALUES (%s::uuid, %s, now())
                ON CONFLICT (user_id) DO UPDATE
                  SET pref = EXCLUDED.pref, updated_at = now()
                """,
                (user_id, body.pref),
            )
        conn.commit()
    finally:
        conn.close()
    return {"pref": body.pref}


# ── LLM preference ──────────────────────────────────────────────

@app.get("/api/users/me/llm-pref")
async def get_llm_pref(user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT llm_pref FROM user_quiz_prefs WHERE user_id = %s::uuid", (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return {"llm_pref": (row[0] if row else "auto")}


class _LlmPrefBody(BaseModel):
    llm_pref: str = Field(..., pattern=r"^(auto|groq|gemini)$")


@app.put("/api/users/me/llm-pref")
async def set_llm_pref(body: _LlmPrefBody, user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_quiz_prefs (user_id, pref, llm_pref, updated_at)
                VALUES (%s::uuid, 'use_video_default', %s, now())
                ON CONFLICT (user_id) DO UPDATE
                  SET llm_pref = EXCLUDED.llm_pref, updated_at = now()
                """,
                (user_id, body.llm_pref),
            )
        conn.commit()
    finally:
        conn.close()
    return {"llm_pref": body.llm_pref}


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

    is_demo = (video_id == DEMO_VIDEO_ID)
    if not is_demo and not _user_has_any_key(user_id):
        raise HTTPException(
            status_code=402,
            detail="Add a Gemini or Groq API key in Settings to generate quizzes for non-demo videos.",
        )

    from pipeline.quiz_cache import get_or_generate

    with _ScopedAPIKeys(user_id, allow_server_fallback=is_demo):
        questions = get_or_generate(video_id, body.end_ts, chunks)

    return {
        "questions": [
            {
                "id": q["id"],
                "question_text": q["question_text"],
                "options": q["options"],
                "difficulty": q.get("difficulty", "medium"),
                "bloom_level": q.get("bloom_level", "understand"),
            }
            for q in questions[: body.count]
        ]
    }


@app.post("/api/quizzes/{question_id}/attempt")
async def submit_attempt(
    question_id: str, body: AttemptRequest, user_id: str = Depends(require_auth)
):
    """Record a quiz attempt; on wrong answer, schedule review for tomorrow.

    Returns ``correct_answer``, the legacy ``explanation`` (= correct option's
    explanation), AND the new ``option_explanations`` map so the UI can show
    why each wrong option is wrong (distractor analysis for learning).

    Pretest questions don't schedule reviews — they're meant to be wrong.
    """
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT correct_answer, explanation, option_explanations, quiz_type
                FROM questions WHERE id = %s
                """,
                (question_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Question not found")

            correct_answer, explanation, option_explanations, quiz_type = row
            is_correct = body.selected_answer == correct_answer
            quiz_type = quiz_type or "end_recall"

            cur.execute(
                """
                INSERT INTO quiz_attempts (id, user_id, question_id, selected_answer, is_correct)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_id, question_id, body.selected_answer, is_correct),
            )

            added_to_review = False
            # Pretests are curiosity hooks — wrong answers are EXPECTED and
            # shouldn't pollute the review queue.
            if not is_correct and quiz_type != "pretest":
                cur.execute(
                    """
                    INSERT INTO review_queue (id, user_id, question_id, next_review_at)
                    VALUES (%s, %s, %s, now() + interval '15 minutes')
                    ON CONFLICT (user_id, question_id) DO UPDATE SET
                        next_review_at = now() + interval '15 minutes',
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
        "option_explanations": option_explanations,
        "quiz_type": quiz_type,
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
                SELECT q.id, q.video_id, v.title, q.question_text, q.options,
                       rq.next_review_at, q.bloom_level
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
                "bloom_level": r[6],
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
            cur.execute("DELETE FROM user_api_keys WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()
    logger.info("Deleted all data for user %s", user_id)
    return {"message": "All your data has been deleted."}


@app.delete("/api/users/me/videos/{video_id}")
async def remove_video_from_library(
    video_id: str,
    user_id: str = Depends(require_auth),
):
    """Soft-delete a single video from the user's library.

    The video and its keyframes/chunks remain globally indexed (so other users
    aren't affected). Only this user's link is hidden by setting
    ``user_videos.deleted_at``.
    """
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_videos
                SET deleted_at = now()
                WHERE user_id = %s AND video_id = %s
                """,
                (user_id, video_id),
            )
            affected = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Video not in your library")
    return {"video_id": video_id, "removed": True}


# ── User-managed API keys (BYOK) ────────────────────────────────


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}…{key[-4:]}"


@app.get("/api/users/me/keys")
async def list_my_keys(user_id: str = Depends(require_auth)):
    """Return which services this user has stored a key for, plus a masked preview."""
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT service, key_value, updated_at FROM user_api_keys WHERE user_id = %s",
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "keys": [
            {"service": r[0], "masked": _mask_key(r[1]), "updated_at": str(r[2])}
            for r in rows
        ]
    }


class _KeyBody(BaseModel):
    service: str = Field(..., pattern=r"^(gemini|groq)$")
    key_value: str = Field(..., min_length=20, max_length=300)


@app.post("/api/users/me/keys")
async def upsert_my_key(body: _KeyBody, user_id: str = Depends(require_auth)):
    """Validate then store a user's API key for a service."""
    # Validate the key by making a tiny test call
    valid, err = _validate_api_key(body.service, body.key_value)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid {body.service} key: {err}")

    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_api_keys (id, user_id, service, key_value, updated_at)
                VALUES (gen_random_uuid(), %s, %s, %s, now())
                ON CONFLICT (user_id, service)
                DO UPDATE SET key_value = EXCLUDED.key_value, updated_at = now()
                """,
                (user_id, body.service, body.key_value),
            )
        conn.commit()
    finally:
        conn.close()
    return {"service": body.service, "masked": _mask_key(body.key_value), "ok": True}


@app.delete("/api/users/me/keys/{service}")
async def delete_my_key(service: str, user_id: str = Depends(require_auth)):
    if service not in ("gemini", "groq"):
        raise HTTPException(status_code=400, detail="Unknown service")
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_api_keys WHERE user_id = %s AND service = %s",
                (user_id, service),
            )
        conn.commit()
    finally:
        conn.close()
    return {"service": service, "deleted": True}


def _validate_api_key(service: str, key_value: str) -> tuple[bool, str | None]:
    """Make a cheap test call to verify the key works. Returns (ok, error_message)."""
    try:
        if service == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=key_value)
            r = client.models.embed_content(
                model="gemini-embedding-2-preview",
                contents="ping",
                config=types.EmbedContentConfig(output_dimensionality=1024),
            )
            if not r.embeddings or len(r.embeddings[0].values) != 1024:
                return False, "Unexpected response shape"
            return True, None
        elif service == "groq":
            from groq import Groq
            client = Groq(api_key=key_value)
            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            if not r.choices:
                return False, "No response"
            return True, None
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        # Surface the most useful chunk of the error
        for marker in ("API key", "Invalid", "expired", "Forbidden", "Unauthorized", "401", "403"):
            if marker.lower() in msg.lower():
                return False, msg[:160]
        return False, msg[:160]
    return False, "Unknown service"


# ── Admin: regenerate quiz cache ─────────────────────────────────


@app.get("/api/users/me/whoami")
async def whoami(token: dict | None = Depends(verify_token)):
    """Lightweight identity probe used by the frontend to enable admin features."""
    if token is None:
        return {"authenticated": False, "is_admin": False, "email": None}
    email = (token.get("email") or "").lower() or None
    is_admin = bool(email and email in _admin_emails())
    return {
        "authenticated": True,
        "is_admin": is_admin,
        "email": email,
        "user_id": token.get("sub"),
    }


@app.post("/api/admin/videos/{video_id}/quiz/regenerate")
async def admin_regenerate_quiz(
    video_id: str,
    user_id: str = Depends(require_admin),
):
    """ADMIN ONLY: wipe the global quiz cache for this video and regenerate
    using the admin's API keys. New questions become the new shared set for
    every user of this video.
    """
    # Pull chunks + checkpoints
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
            cur.execute(
                "SELECT timestamp_seconds FROM checkpoints WHERE video_id = %s ORDER BY timestamp_seconds",
                (video_id,),
            )
            cp_timestamps = [float(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()

    if not chunks:
        raise HTTPException(status_code=404, detail="Video not indexed yet")
    if not cp_timestamps:
        raise HTTPException(status_code=404, detail="Video has no checkpoints")

    # Wipe existing cache for this video
    conn = psycopg2.connect(_get_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM quiz_attempts WHERE question_id IN (SELECT id FROM questions WHERE video_id = %s)",
                (video_id,),
            )
            cur.execute(
                "DELETE FROM review_queue WHERE question_id IN (SELECT id FROM questions WHERE video_id = %s)",
                (video_id,),
            )
            cur.execute("DELETE FROM questions WHERE video_id = %s", (video_id,))
        conn.commit()
    finally:
        conn.close()

    # Regenerate using admin's keys (batched single LLM call)
    from pipeline.quiz_gen import generate_quizzes_for_checkpoints
    from pipeline.quiz_cache import cache_questions

    with _ScopedAPIKeys(user_id, allow_server_fallback=False):
        results = generate_quizzes_for_checkpoints(video_id, cp_timestamps, chunks)

    total = 0
    for ts, questions in results.items():
        if questions:
            cache_questions(video_id, int(ts // 30), 1, questions)
            total += len(questions)

    return {
        "video_id": video_id,
        "checkpoints": len(cp_timestamps),
        "questions_generated": total,
        "message": f"Regenerated {total} questions across {len(cp_timestamps)} checkpoints (will be shared with all users).",
    }
