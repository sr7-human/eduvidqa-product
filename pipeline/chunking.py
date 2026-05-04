"""Adaptive transcript chunking with keyframe linking.

Splits the YouTube transcript into fixed-duration non-overlapping windows
(default 10s; auto-grows for very long videos to keep the embedding-API
call count manageable on free-tier quotas).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)


def _adaptive_chunk_seconds(total_duration: float) -> float:
    """Pick a chunk size that keeps embedding calls bounded.

    Heuristic: aim for roughly <= 600 chunks per video (= ~6 batched embed
    requests on Gemini's 100-per-batch limit).

    | Video length        | Chunk size |
    |---------------------|-----------|
    | <= 1 hour           | 10 s       |
    | 1 – 2 hours         | 30 s       |
    | 2 – 4 hours         | 60 s       |
    | > 4 hours           | 120 s      |
    """
    if total_duration <= 3600:        # 1 hr
        return 10.0
    if total_duration <= 7200:        # 2 hr
        return 30.0
    if total_duration <= 14400:       # 4 hr
        return 60.0
    return 120.0


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
    # Strategy:
    #   1. Try English variants first (best quality for embeddings/QA).
    #   2. Else try common Indian languages directly.
    #   3. Else list every available track and translate to English when the
    #      track is translatable; otherwise just take it as-is.
    api = YouTubeTranscriptApi()
    PREFERRED = ["en", "en-US", "en-GB"]
    FALLBACK = ["hi", "hi-IN", "bn", "ta", "te", "ml", "mr", "gu", "kn", "pa", "ur"]

    fetched = None
    primary_exc: Exception | None = None
    try:
        fetched = api.fetch(video_id, languages=PREFERRED + FALLBACK)
        chosen_lang = getattr(fetched, "language_code", "?")
        if chosen_lang not in PREFERRED:
            logger.info(
                "No English transcript for %s; using %s as-is",
                video_id, chosen_lang,
            )
    except Exception as exc:
        primary_exc = exc

    # ── 2. Discovery + auto-translate fallback ──────────────────────
    if fetched is None:
        try:
            transcript_list = api.list(video_id)
            # Collect available tracks. The API exposes both manually-created
            # and auto-generated tracks via the same iterator.
            tracks = list(transcript_list)
            if not tracks:
                raise primary_exc or RuntimeError("No transcripts available")

            # Prefer a translatable track so we end up with English text.
            translatable = next((t for t in tracks if getattr(t, "is_translatable", False)), None)
            if translatable is not None:
                try:
                    translated = translatable.translate("en")
                    fetched = translated.fetch()
                    logger.info(
                        "Translated %s transcript (%s) → English for %s",
                        "auto" if getattr(translatable, "is_generated", False) else "manual",
                        getattr(translatable, "language_code", "?"),
                        video_id,
                    )
                except Exception as t_exc:
                    logger.warning("Translate→en failed for %s: %s", video_id, t_exc)

            # Last resort: fetch the first available track in its native language.
            if fetched is None:
                first = tracks[0]
                fetched = first.fetch()
                logger.warning(
                    "Using untranslated %s transcript for %s",
                    getattr(first, "language_code", "?"), video_id,
                )
        except Exception as fallback_exc:
            # Surface the most informative error.
            if primary_exc is not None:
                raise primary_exc from fallback_exc
            raise
    # Normalise to list[dict] for uniform access
    transcript = [
        {"text": s.text, "start": s.start, "duration": s.duration}
        for s in fetched
    ]
    if not transcript:
        raise RuntimeError(f"Empty transcript for video {video_id}")

    # ── 2. Determine total duration → adaptive window size ─────────
    last = transcript[-1]
    total_duration = last["start"] + last.get("duration", 0.0)
    chunk_seconds = _adaptive_chunk_seconds(total_duration)
    n_chunks = math.ceil(total_duration / chunk_seconds)
    if chunk_seconds > 10.0:
        logger.info(
            "Long video (%.0fs) — using %.0fs chunks → %d total (saves embed calls)",
            total_duration, chunk_seconds, n_chunks,
        )

    # ── 3. Bin transcript lines into windows ─────────────────────────
    chunks: list[dict] = []
    for i in range(n_chunks):
        start = i * chunk_seconds
        end = start + chunk_seconds
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
