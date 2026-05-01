"""Extract THE frame at the user's exact timestamp.

Strategy (best → worst):
1. Cached MP4 on disk → seek to exact second with OpenCV (instant, accurate to 1s).
2. yt-dlp fragment download → grab a 6-second slice around the timestamp,
   extract the exact frame, delete the slice. Slower (~2-5s) but accurate.
3. Nearest stored keyframe (Supabase URL or local path). Up to ~5s off,
   but always available (we ALWAYS upload these to Supabase during ingest).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_live_frame(
    video_id: str,
    timestamp: float,
    data_dir: str = "data/processed",
) -> str | None:
    """Return path/URL of the best available frame at *timestamp*."""
    # ── Strategy 1: Cached MP4 still on disk ────────────────────────
    videos_dir = Path(data_dir).parent / "videos" / video_id
    mp4_files = list(videos_dir.glob("*.mp4")) if videos_dir.is_dir() else []
    if mp4_files:
        out = _frame_from_mp4(mp4_files[0], timestamp, video_id)
        if out:
            return out

    # ── Strategy 2: Fragment download (TRUE live frame) ────────────
    out = _frame_via_fragment_download(video_id, timestamp)
    if out:
        return out

    # ── Strategy 3: Nearest stored keyframe from DB ────────────────
    return _nearest_db_keyframe(video_id, timestamp)


# ── Strategy 1 ────────────────────────────────────────────────────


def _frame_from_mp4(mp4_path: Path, timestamp: float, video_id: str) -> str | None:
    try:
        import cv2
    except ImportError:
        logger.warning("OpenCV unavailable")
        return None
    cap = cv2.VideoCapture(str(mp4_path))
    if not cap.isOpened():
        return None
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            return None
        out_dir = Path(tempfile.gettempdir()) / "eduvidqa-live"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{video_id}_{int(timestamp)}.jpg"
        cv2.imwrite(str(out_path), frame)
        logger.info("Live frame from cached MP4 at %.1fs", timestamp)
        return str(out_path)
    finally:
        cap.release()


# ── Strategy 2 ────────────────────────────────────────────────────


def _frame_via_fragment_download(video_id: str, timestamp: float) -> str | None:
    """Use yt-dlp + ffmpeg to download a tiny slice around *timestamp*, then extract one frame.

    Total cost: ~2-5 sec extra latency, ~1-3 MB temp download.
    Requires ffmpeg + yt-dlp on PATH (both already in the Docker image).
    """
    try:
        import yt_dlp
        from yt_dlp.networking.impersonate import ImpersonateTarget
    except ImportError:
        logger.warning("yt_dlp unavailable")
        return None

    work_dir = Path(tempfile.mkdtemp(prefix="eduvidqa-frag-"))
    try:
        # Download a 6-second slice centred on the timestamp (yt-dlp downloads
        # whatever covers the requested time range; ffmpeg trims it).
        start = max(0, int(timestamp) - 1)
        end = int(timestamp) + 5
        slice_path = work_dir / "slice.mp4"
        ydl_opts = {
            "format": "bestvideo[height<=480][ext=mp4]/best[height<=480]/best",
            "outtmpl": str(slice_path),
            "quiet": True,
            "no_warnings": True,
            "no_playlist": True,
            "impersonate": ImpersonateTarget("chrome"),
            "download_ranges": _make_range_func(start, end),
            "force_keyframes_at_cuts": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        # Find whatever file landed (yt-dlp may add extension)
        candidates = sorted(work_dir.glob("slice*"), key=lambda p: p.stat().st_size, reverse=True)
        if not candidates:
            logger.warning("Fragment download produced no file")
            return None
        slice_file = candidates[0]

        # Extract single frame at (timestamp - start) seconds into the slice
        offset = max(0, timestamp - start)
        out_dir = Path(tempfile.gettempdir()) / "eduvidqa-live"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{video_id}_{int(timestamp)}.jpg"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{offset:.3f}",
            "-i", str(slice_file),
            "-frames:v", "1", "-q:v", "3",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            logger.warning("ffmpeg frame extract failed: %s", result.stderr.decode()[:200])
            return None
        logger.info("Live frame via fragment download at %.1fs (%.1fkB)", timestamp, out_path.stat().st_size / 1024)
        return str(out_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fragment download failed: %s", str(exc)[:200])
        return None
    finally:
        # Clean up temp slice (keep only the extracted frame)
        try:
            shutil.rmtree(work_dir)
        except Exception:
            pass


def _make_range_func(start: int, end: int):
    """Build the download_ranges callable yt-dlp expects."""
    def _ranges(info_dict, ydl):
        return [{"start_time": start, "end_time": end}]
    return _ranges


# ── Strategy 3 ────────────────────────────────────────────────────


def _nearest_db_keyframe(video_id: str, timestamp: float) -> str | None:
    """Look up the closest keyframe by timestamp from the keyframe_embeddings table."""
    try:
        import psycopg2
    except ImportError:
        return None
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        return None
    try:
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT storage_path, timestamp_seconds
                    FROM keyframe_embeddings
                    WHERE video_id = %s
                    ORDER BY ABS(timestamp_seconds - %s)
                    LIMIT 1
                    """,
                    (video_id, timestamp),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if row:
            path, ts = row
            logger.info(
                "Nearest stored keyframe to %.1fs: %s (Δ=%.1fs)",
                timestamp, str(path)[:80], abs(float(ts) - timestamp),
            )
            return path
    except Exception as exc:
        logger.warning("DB keyframe lookup failed: %s", exc)
    return None
