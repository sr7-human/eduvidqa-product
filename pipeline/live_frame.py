"""Extract a frame at the exact timestamp the student asked about.

Falls back to the nearest stored keyframe if the .mp4 is unavailable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_live_frame(
    video_id: str,
    timestamp: float,
    data_dir: str = "data/processed",
) -> str | None:
    """Find the nearest stored keyframe to *timestamp*.

    1. If the video .mp4 still exists → extract exact frame with OpenCV.
    2. Otherwise → find nearest keyframe from manifest.json.

    Returns the path to the frame image, or ``None`` if nothing found.
    """
    base = Path(data_dir) / video_id

    # ── Try extracting the exact frame from .mp4 ──────────────────────
    videos_dir = Path(data_dir).parent / "videos" / video_id
    mp4_files = list(videos_dir.glob("*.mp4")) if videos_dir.is_dir() else []
    if mp4_files:
        mp4_path = mp4_files[0]
        frame_path = _extract_frame_opencv(mp4_path, timestamp, base)
        if frame_path:
            return frame_path

    # ── Fallback: nearest stored keyframe ─────────────────────────────
    manifest_path = base / "keyframes" / "manifest.json"
    if not manifest_path.is_file():
        logger.warning("No keyframe manifest for %s", video_id)
        return None

    with open(manifest_path) as f:
        manifest: list[dict] = json.load(f)

    if not manifest:
        return None

    # Find the keyframe with the smallest time delta
    best = min(manifest, key=lambda kf: abs(kf["timestamp"] - timestamp))
    frame_file = best["file"]

    # Handle both absolute and relative paths
    p = Path(frame_file)
    if p.is_file():
        logger.info("Nearest keyframe to %.1fs: %s (Δ=%.1fs)", timestamp, p.name, abs(best["timestamp"] - timestamp))
        return str(p)

    # Try relative to data_dir
    rel = Path(data_dir).parent / frame_file
    if rel.is_file():
        return str(rel)

    logger.warning("Keyframe file not found: %s", frame_file)
    return None


def _extract_frame_opencv(
    mp4_path: Path,
    timestamp: float,
    output_dir: Path,
) -> str | None:
    """Extract a single frame at *timestamp* from *mp4_path* using OpenCV."""
    try:
        import cv2
    except ImportError:
        logger.warning("OpenCV not available — cannot extract live frame from .mp4")
        return None

    cap = cv2.VideoCapture(str(mp4_path))
    if not cap.isOpened():
        logger.warning("Cannot open video: %s", mp4_path)
        return None

    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            return None

        out_path = output_dir / "keyframes" / f"live_{int(timestamp)}.jpg"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), frame)
        logger.info("Extracted live frame at %.1fs → %s", timestamp, out_path)
        return str(out_path)
    finally:
        cap.release()
