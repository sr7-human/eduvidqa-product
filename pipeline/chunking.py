"""10-second transcript chunking with keyframe linking.

Downloads the YouTube transcript and groups it into fixed 10-second
non-overlapping windows, linking any keyframes that fall within each window.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)


def chunk_transcript(
    video_id: str,
    output_dir: str = "data/processed",
    keyframe_manifest: list[dict] | None = None,
) -> list[dict]:
    """Download transcript and split into 10-second chunks.

    Parameters
    ----------
    video_id : str
        YouTube video ID.
    output_dir : str
        Root output directory.  Files land in
        ``{output_dir}/{video_id}/transcript/``.
    keyframe_manifest : list[dict] | None
        Keyframe dicts (as returned by ``extract_keyframes``).  Each
        keyframe is linked to the chunk whose window contains its timestamp.

    Returns
    -------
    list[dict]
        One dict per chunk::

            {
                "chunk_id": "chunk_003",
                "start_time": 30.0,
                "end_time": 40.0,
                "text": "the insertion sort algorithm works by...",
                "linked_keyframe_ids": ["kf_000035"]
            }
    """
    # ── 1. Fetch transcript ──────────────────────────────────────────
    # Try English first (preferred). If unavailable, fall back to ANY
    # available language — Gemini answer/embedding handles non-English text.
    api = YouTubeTranscriptApi()
    fetched = None
    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except Exception as primary_exc:
        try:
            transcript_list = api.list(video_id)
            available_codes: list[str] = []
            for t in transcript_list:
                code = getattr(t, "language_code", None)
                if code:
                    available_codes.append(code)
            if available_codes:
                logger.warning(
                    "No English transcript for %s; falling back to %s",
                    video_id, available_codes[0],
                )
                fetched = api.fetch(video_id, languages=available_codes)
            else:
                raise primary_exc
        except Exception:
            raise primary_exc
    # Normalise to list[dict] for uniform access
    transcript = [
        {"text": s.text, "start": s.start, "duration": s.duration}
        for s in fetched
    ]
    if not transcript:
        raise RuntimeError(f"Empty transcript for video {video_id}")

    # ── 2. Determine total duration → number of 10-s windows ────────
    last = transcript[-1]
    total_duration = last["start"] + last.get("duration", 0.0)
    n_chunks = math.ceil(total_duration / 10.0)

    # ── 3. Bin transcript lines into windows ─────────────────────────
    chunks: list[dict] = []
    for i in range(n_chunks):
        start = i * 10.0
        end = start + 10.0
        # Collect all lines whose start falls in [start, end)
        lines = [
            entry["text"]
            for entry in transcript
            if start <= entry["start"] < end
        ]
        text = " ".join(lines).strip()

        # Link keyframes
        linked: list[str] = []
        if keyframe_manifest:
            linked = [
                kf["frame_id"]
                for kf in keyframe_manifest
                if start <= kf["timestamp"] < end
            ]

        chunks.append(
            {
                "chunk_id": f"chunk_{i:03d}",
                "start_time": start,
                "end_time": end,
                "text": text,
                "linked_keyframe_ids": linked,
            }
        )

    # ── 4. Save outputs ─────────────────────────────────────────────
    tx_dir = Path(output_dir) / video_id / "transcript"
    tx_dir.mkdir(parents=True, exist_ok=True)

    # Full transcript as plain text
    full_text = " ".join(entry["text"] for entry in transcript)
    (tx_dir / "full.txt").write_text(full_text, encoding="utf-8")

    # Structured chunks
    (tx_dir / "chunks.json").write_text(
        json.dumps(chunks, indent=2), encoding="utf-8"
    )

    logger.info(
        "Chunking: %d chunks from %s (%.1fs total)",
        len(chunks),
        video_id,
        total_duration,
    )
    return chunks
