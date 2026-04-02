"""SSIM-based keyframe extraction from lecture videos.

Extracts 1 frame per second, keeps only those that differ significantly
(SSIM < threshold) from the last kept frame.

Adaptive mode: if keyframes/minute exceeds a density cap after the first
pass, the module automatically re-runs with a lower threshold and then
caps keyframes per 10-second chunk — keeping only the most visually
distinct frames in each window.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

# Adaptive defaults
_MAX_KF_PER_MIN = 10          # Above this → video is "high-change"
_ADAPTIVE_THRESHOLD = 0.80    # Lower SSIM bar for high-change videos
_MAX_KF_PER_CHUNK = 3         # Keep at most 3 per 10-second window
_SSIM_RESIZE_WIDTH = 256      # Resize before SSIM to reduce cursor/noise sensitivity


def _resize_for_ssim(gray: np.ndarray, width: int = _SSIM_RESIZE_WIDTH) -> np.ndarray:
    """Downsample a grayscale frame for more robust SSIM comparison."""
    h, w = gray.shape[:2]
    if w <= width:
        return gray
    ratio = width / w
    return cv2.resize(gray, (width, int(h * ratio)), interpolation=cv2.INTER_AREA)


def extract_keyframes(
    video_path: str,
    video_id: str,
    output_dir: str = "data/processed",
    threshold: float = 0.92,
    adaptive: bool = True,
) -> list[dict]:
    """Extract unique keyframes from *video_path* using SSIM deduplication.

    Parameters
    ----------
    video_path : str
        Path to the .mp4 file.
    video_id : str
        YouTube video ID (used for output folder naming).
    output_dir : str
        Root output directory.  Keyframes land in
        ``{output_dir}/{video_id}/keyframes/``.
    threshold : float
        SSIM threshold.  Frames with SSIM > threshold relative to the
        previous kept frame are considered duplicates and skipped.
    adaptive : bool
        If True (default), automatically detect high-change videos
        (>10 keyframes/min) and re-run with lower threshold + capping.

    Returns
    -------
    list[dict]
        One dict per kept frame::

            {
                "frame_id": "kf_000035",
                "timestamp": 35,
                "file": "data/processed/{video_id}/keyframes/kf_000035.jpg",
                "ssim_score": 0.847
            }
    """
    kept, duration_s = _extract_pass(video_path, video_id, output_dir, threshold)
    duration_min = duration_s / 60.0 if duration_s > 0 else 1.0
    kf_per_min = len(kept) / duration_min

    if adaptive and kf_per_min > _MAX_KF_PER_MIN:
        logger.info(
            "Adaptive mode: %.1f kf/min exceeds cap (%d). "
            "Re-running with threshold=%.2f + resize=%dpx + cap=%d/chunk",
            kf_per_min, _MAX_KF_PER_MIN,
            _ADAPTIVE_THRESHOLD, _SSIM_RESIZE_WIDTH, _MAX_KF_PER_CHUNK,
        )
        # Clean up first-pass files
        kf_dir = Path(output_dir) / video_id / "keyframes"
        if kf_dir.exists():
            shutil.rmtree(kf_dir)

        # Second pass: lower threshold + downsampled SSIM
        kept, duration_s = _extract_pass(
            video_path, video_id, output_dir,
            threshold=_ADAPTIVE_THRESHOLD,
            resize_for_ssim=True,
        )

        # Cap: keep only the N most distinct per 10-second window
        kept = _cap_per_chunk(kept, chunk_seconds=10, max_per_chunk=_MAX_KF_PER_CHUNK)

        # Remove files for frames that got capped out
        kept_files = {k["file"] for k in kept}
        kf_dir = Path(output_dir) / video_id / "keyframes"
        for jpg in kf_dir.glob("kf_*.jpg"):
            if str(jpg) not in kept_files:
                jpg.unlink()

        logger.info(
            "Adaptive result: %d keyframes (was %d before capping)",
            len(kept),
            int(kf_per_min * duration_min),
        )

    # Write manifest
    manifest_path = Path(output_dir) / video_id / "keyframes" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(kept, indent=2))

    logger.info(
        "Keyframes: %d kept from %d sampled (video %s, %.1fs)",
        len(kept), duration_s, video_id, duration_s,
    )
    return kept


def _extract_pass(
    video_path: str,
    video_id: str,
    output_dir: str,
    threshold: float,
    resize_for_ssim: bool = False,
) -> tuple[list[dict], int]:
    """Single extraction pass. Returns (kept_frames, duration_seconds)."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = int(total_frames / fps) if fps > 0 else 0

    kf_dir = Path(output_dir) / video_id / "keyframes"
    kf_dir.mkdir(parents=True, exist_ok=True)

    kept: list[dict] = []
    prev_gray: np.ndarray | None = None

    for sec in range(duration_s):
        frame_pos = int(sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cmp_gray = _resize_for_ssim(gray) if resize_for_ssim else gray

        if prev_gray is None:
            score = 0.0
        else:
            score = ssim(prev_gray, cmp_gray)

        if score > threshold:
            continue

        frame_id = f"kf_{sec:06d}"
        out_path = kf_dir / f"{frame_id}.jpg"
        cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        kept.append(
            {
                "frame_id": frame_id,
                "timestamp": sec,
                "file": str(out_path),
                "ssim_score": round(float(score), 4),
            }
        )
        prev_gray = cmp_gray

    cap.release()
    return kept, duration_s


def _cap_per_chunk(
    keyframes: list[dict],
    chunk_seconds: int = 10,
    max_per_chunk: int = _MAX_KF_PER_CHUNK,
) -> list[dict]:
    """Keep only the *max_per_chunk* most visually distinct frames per window.

    "Most distinct" = lowest SSIM score (biggest change from predecessor).
    """
    if not keyframes:
        return []

    from collections import defaultdict
    buckets: dict[int, list[dict]] = defaultdict(list)
    for kf in keyframes:
        bucket = int(kf["timestamp"] // chunk_seconds)
        buckets[bucket].append(kf)

    result: list[dict] = []
    for bucket_id in sorted(buckets):
        group = buckets[bucket_id]
        # Sort by ssim ascending → most distinct first
        group.sort(key=lambda k: k["ssim_score"])
        result.extend(group[:max_per_chunk])

    # Restore chronological order
    result.sort(key=lambda k: k["timestamp"])
    return result
