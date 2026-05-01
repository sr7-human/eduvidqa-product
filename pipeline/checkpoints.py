"""Place quiz checkpoints at topic-shift boundaries."""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_MIN_SPACING_SECONDS = 180.0
_MIN_VIDEO_DURATION = 60.0  # below this we don't bother placing checkpoints


def _topic_label(text: str) -> str:
    words = (text or "").split()
    if not words:
        return "(untitled)"
    snippet = " ".join(words[:8])
    return snippet + ("..." if len(words) > 8 else "")


def _cosine_distance(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(1.0 - np.dot(a, b) / (na * nb))


def _length_shift(prev_text: str, curr_text: str) -> float:
    """Proxy shift score using normalized text-length delta."""
    p = len(prev_text or "")
    c = len(curr_text or "")
    denom = max(p, c, 1)
    return abs(p - c) / denom


def place_checkpoints(
    chunks: list[dict],
    video_duration_seconds: float,
    embeddings: list | None = None,
    target_interval_minutes: float = 6.0,
) -> list[dict]:
    """Place checkpoints at semantic boundaries, ~1 per 5-8 minutes.

    Returns list of dicts with keys:
    ``timestamp_seconds``, ``chunk_index``, ``topic_label``, ``shift_score``.
    """
    if not chunks or video_duration_seconds < _MIN_VIDEO_DURATION:
        return []

    target_interval_sec = max(60.0, target_interval_minutes * 60.0)
    target_count = max(1, round(video_duration_seconds / target_interval_sec))
    target_count = min(target_count, max(1, len(chunks) - 1))

    # Compute shift score for each chunk (vs previous). chunk 0 has shift 0.
    shifts: list[float] = [0.0]
    for i in range(1, len(chunks)):
        if embeddings is not None and i < len(embeddings) and embeddings[i - 1] is not None:
            shifts.append(_cosine_distance(embeddings[i - 1], embeddings[i]))
        else:
            shifts.append(_length_shift(chunks[i - 1].get("text", ""), chunks[i].get("text", "")))

    # Candidates sorted by shift desc, skip index 0 (no prior chunk).
    candidates = sorted(
        ((i, shifts[i]) for i in range(1, len(chunks))),
        key=lambda x: x[1],
        reverse=True,
    )

    selected: list[dict] = []
    for idx, score in candidates:
        if len(selected) >= target_count:
            break
        ts = float(chunks[idx].get("start_time", 0.0))
        if any(abs(ts - cp["timestamp_seconds"]) < _MIN_SPACING_SECONDS for cp in selected):
            continue
        selected.append({
            "timestamp_seconds": ts,
            "chunk_index": idx,
            "topic_label": _topic_label(chunks[idx].get("text", "")),
            "shift_score": float(score),
        })

    selected.sort(key=lambda cp: cp["timestamp_seconds"])
    return selected
