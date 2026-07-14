"""Extract THE frame at the user's exact timestamp.

Strategy (in order):
1. Cached MP4 on disk → seek to exact second with OpenCV (instant, accurate).
2. yt-dlp fragment download for a TRUE live frame at the exact second (720p,
   crisp). ON by default (LIVE_FRAME_YT_DOWNLOAD=1); needs deno + yt-dlp-ejs to
   solve YouTube's JS challenge. Set LIVE_FRAME_YT_DOWNLOAD=0 to skip it.
3. Nearest stored keyframe (Supabase URL) — always-available fallback. Up to
   ~10s off, no per-question YouTube call, scales to every user.

Note: a user-pasted screenshot (handled upstream in the API) always wins over
all of these.
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
    # ON by default again (2026-07-14): YouTube's SABR + "n" JS-challenge that
    # broke this is now solved by yt-dlp-ejs + a deno runtime (see
    # pipeline.ingest.get_cookie_ydl_opts), so range downloads work and give a
    # crisp 720p frame at the exact second. Set LIVE_FRAME_YT_DOWNLOAD=0 to
    # disable (falls back to the dense stored keyframes).
    if os.getenv("LIVE_FRAME_YT_DOWNLOAD", "1") == "1":
        out = _frame_via_fragment_download(video_id, timestamp)
        if out:
            return out

    # ── Strategy 3: Nearest stored keyframe from DB (default) ──────
    return _nearest_db_keyframe(video_id, timestamp)


# ── Content crop (on-demand, one vision call per question) ───────────────

_GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_CROP_PROMPT = (
    "This is a single frame from a lecture video. Return ONLY the bounding box of "
    "the main TEACHING CONTENT area — the whiteboard, blackboard, or projected "
    "slide/screen that has the text/writing/diagram. EXCLUDE the presenter, the "
    "students/audience, furniture and the room. Respond with EXACTLY four numbers "
    "x0,y0,x1,y1 as fractions of image width/height in [0,1], comma-separated, and "
    "nothing else. If the content already fills the frame or there is no such area, "
    "respond: none"
)


def _read_frame_bytes(path: str) -> bytes | None:
    try:
        if path.startswith(("http://", "https://")):
            import urllib.request
            with urllib.request.urlopen(path, timeout=10) as r:
                return r.read()
        with open(path, "rb") as fh:
            return fh.read()
    except Exception:
        return None


def crop_to_content(path: str | None, groq_api_key: str | None) -> str | None:
    """Crop ONE frame to its teaching-content region (board/slide/screen) using a
    vision LLM. One call per question — cheap and on-demand (vs. cropping every
    stored keyframe). Returns a NEW local path, or the original path unchanged on
    any failure / low-confidence result (never an empty/garbage crop).

    Disable with CROP_ANSWER_FRAME=0.
    """
    if not path or not groq_api_key or os.getenv("CROP_ANSWER_FRAME", "1") == "0":
        return path
    raw = _read_frame_bytes(path)
    if not raw:
        return path
    try:
        import base64
        import re
        import uuid

        import cv2
        import numpy as np

        arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            return path
        H, W = arr.shape[:2]
        b64 = base64.b64encode(raw).decode()
        from groq import Groq
        client = Groq(api_key=groq_api_key)
        resp = client.chat.completions.create(
            model=_GROQ_VISION_MODEL, temperature=0.0, max_tokens=40,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": _CROP_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}],
        )
        out = (resp.choices[0].message.content or "").strip()
        if out.lower().startswith("none"):
            return path
        nums = [float(x) for x in re.findall(r"[0-9]*\.?[0-9]+", out)][:4]
        if len(nums) != 4:
            return path
        x0f, x1f = sorted((max(0.0, min(1.0, nums[0])), max(0.0, min(1.0, nums[2]))))
        y0f, y1f = sorted((max(0.0, min(1.0, nums[1])), max(0.0, min(1.0, nums[3]))))
        x0, y0, x1, y1 = int(x0f * W), int(y0f * H), int(x1f * W), int(y1f * H)
        cov = ((x1 - x0) * (y1 - y0)) / float(W * H)
        # Reject absurd crops — keep the full frame instead.
        if cov < 0.05 or cov > 0.98 or (x1 - x0) < 32 or (y1 - y0) < 32:
            return path
        crop = arr[y0:y1, x0:x1]
        out_dir = Path(tempfile.gettempdir()) / "eduvidqa-crop"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{uuid.uuid4().hex}.jpg"
        cv2.imwrite(str(out_path), crop)
        logger.info("Cropped answer frame to content region (%.0f%% of frame)", cov * 100)
        return str(out_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("content crop failed (non-fatal, using full frame): %s", exc)
        return path


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
            # 720p avc (format 136) is video-only, crisp and OpenCV/ffmpeg-friendly;
            # fall back through smaller heights if it's ever unavailable.
            "format": "136/bestvideo[height<=720]/best[height<=720]/best/worst",
            "outtmpl": str(slice_path),
            "quiet": True,
            "no_warnings": True,
            "no_playlist": True,
            "impersonate": ImpersonateTarget("chrome"),
            "download_ranges": _make_range_func(start, end),
            "force_keyframes_at_cuts": True,
            # Ask for player clients that still expose plain https (range-able)
            # formats — YouTube's SABR-only experiment otherwise hides them and
            # the range download fails with "Requested format is not available".
            "extractor_args": {"youtube": {"player_client": ["web_safari", "web", "tv", "android", "ios"]}},
        }
        # Authenticate to YouTube (browser cookies / cookies.txt) so it stops
        # blocking fragment downloads with the "not a bot" challenge.
        try:
            from pipeline.ingest import get_cookie_ydl_opts
            ydl_opts.update(get_cookie_ydl_opts())
        except Exception:
            pass
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
