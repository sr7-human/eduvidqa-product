"""Video ingestion pipeline: YouTube URL → transcript + frames → chunked segments."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .models import IngestResult, VideoMetadata, VideoSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})"
)


def parse_video_id(youtube_url: str) -> str:
    """Extract the 11-character video ID from a URL or bare ID."""
    m = _YT_URL_RE.search(youtube_url)
    if m:
        return m.group(1)
    # Maybe it's already a bare video ID
    if re.fullmatch(r"[\w-]{11}", youtube_url):
        return youtube_url
    raise ValueError(f"Cannot parse YouTube video ID from: {youtube_url}")


def _get_video_info(video_id: str) -> dict:
    """Fetch basic video metadata without yt-dlp (fast, no hang)."""
    # Just return minimal info — we get duration from transcript entries
    return {"title": f"Video {video_id}", "duration": 0, "channel": "YouTube"}


# ---------------------------------------------------------------------------
# Transcript extraction
# ---------------------------------------------------------------------------


def extract_transcript(video_id: str) -> tuple[list[dict], str]:
    """Get transcript entries. Tries captions API first, falls back to Whisper.

    Returns:
        (entries, source) where entries = [{"text": ..., "start": ..., "duration": ...}, ...]
        and source is "captions" or "whisper".
    """
    # --- Attempt 1: youtube-transcript-api (fast, no download) ---
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        entries = [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in transcript.snippets
        ]
        if entries:
            logger.info("Transcript obtained via captions API (%d entries)", len(entries))
            return entries, "captions"
    except Exception as exc:
        logger.info("Captions unavailable (%s), falling back to Whisper", exc)

    # --- Attempt 2: Whisper (download audio → transcribe) ---
    return _whisper_transcribe(video_id), "whisper"


def _whisper_transcribe(video_id: str) -> list[dict]:
    """Download audio with yt-dlp and transcribe via openai-whisper (small model)."""
    import whisper  # lazy import — heavy dependency

    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.m4a")
        try:
            import yt_dlp
            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio",
                "outtmpl": audio_path,
                "no_playlist": True,
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            raise RuntimeError(f"Audio download failed: {e}")
        model = whisper.load_model("small")
        result = model.transcribe(audio_path)

    entries = []
    for seg in result.get("segments", []):
        entries.append(
            {
                "text": seg["text"].strip(),
                "start": seg["start"],
                "duration": seg["end"] - seg["start"],
            }
        )
    logger.info("Whisper transcription complete (%d segments)", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Transcript chunking
# ---------------------------------------------------------------------------


def chunk_transcript(
    transcript_entries: list[dict],
    chunk_duration: float = 120.0,
) -> list[dict]:
    """Group transcript entries into fixed-duration chunks.

    Returns list of {"start": float, "end": float, "text": str}.
    """
    if not transcript_entries:
        return []

    chunks: list[dict] = []
    current_start = transcript_entries[0]["start"]
    current_texts: list[str] = []
    current_end = current_start

    for entry in transcript_entries:
        entry_start = entry["start"]
        entry_end = entry_start + entry.get("duration", 0.0)

        # If this entry would push us past the chunk boundary, finalize chunk
        if entry_start - current_start >= chunk_duration and current_texts:
            chunks.append(
                {
                    "start": current_start,
                    "end": current_end,
                    "text": " ".join(current_texts),
                }
            )
            current_start = entry_start
            current_texts = []

        current_texts.append(entry["text"])
        current_end = max(current_end, entry_end)

    # Final (possibly partial) chunk
    if current_texts:
        chunks.append(
            {
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_texts),
            }
        )

    return chunks


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------


def extract_frames(
    video_id: str,
    timestamps: list[float],
    output_dir: str,
) -> list[str]:
    """Extract and resize frames at given timestamps.

    Downloads the video once (360p), then uses ffmpeg to seek & grab frames.
    Saved as JPEG, max 512px width, quality 80.

    Returns list of saved JPEG paths (may be empty if tools unavailable).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Check if yt-dlp and ffmpeg are available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("ffmpeg not found — skipping frame extraction")
        return []

    # Download video once (low quality)
    url = f"https://www.youtube.com/watch?v={video_id}"
    video_path = out / f"{video_id}.mp4"
    if not video_path.exists():
        try:
            logger.info("Downloading video (360p) for frame extraction …")
            import yt_dlp
            ydl_opts = {
                "format": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
                "outtmpl": str(video_path),
                "no_playlist": True,
                "merge_output_format": "mp4",
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logger.warning("Video download failed (%s) — skipping frames", e)
            return []

    frame_paths: list[str] = []
    for ts in timestamps:
        fname = f"frame_{ts:07.1f}s.jpg"
        frame_file = out / fname
        if frame_file.exists():
            frame_paths.append(str(frame_file))
            continue

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(ts),
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(frame_file),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
            _resize_frame(str(frame_file), max_width=512, quality=80)
            frame_paths.append(str(frame_file))
        except Exception as e:
            logger.warning("Frame extraction failed for ts=%s: %s", ts, e)

    return frame_paths


def _resize_frame(path: str, max_width: int = 512, quality: int = 80) -> None:
    """Resize JPEG in-place so width <= max_width."""
    with Image.open(path) as img:
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        img.save(path, "JPEG", quality=quality)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_CACHE_META = "metadata.json"
_CACHE_SEGMENTS = "segments.json"


def _load_cache(cache_dir: Path) -> IngestResult | None:
    """Load a previously cached IngestResult, or None."""
    meta_path = cache_dir / _CACHE_META
    seg_path = cache_dir / _CACHE_SEGMENTS
    if not meta_path.exists() or not seg_path.exists():
        return None
    try:
        metadata = VideoMetadata.model_validate_json(meta_path.read_text())
        segments = [
            VideoSegment.model_validate(s)
            for s in json.loads(seg_path.read_text())
        ]
        logger.info("Loaded from cache: %s", cache_dir)
        return IngestResult(metadata=metadata, segments=segments)
    except Exception as exc:
        logger.warning("Cache read failed (%s), re-processing", exc)
        return None


def _save_cache(cache_dir: Path, result: IngestResult) -> None:
    """Persist an IngestResult to disk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / _CACHE_META).write_text(result.metadata.model_dump_json(indent=2))
    (cache_dir / _CACHE_SEGMENTS).write_text(
        json.dumps([s.model_dump() for s in result.segments], indent=2)
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def ingest_video(
    youtube_url: str,
    output_dir: str = "./data",
) -> IngestResult:
    """Full pipeline: URL → transcript + frames → chunked segments.

    Caches results under ``output_dir/{video_id}/``.
    """
    video_id = parse_video_id(youtube_url)
    cache_dir = Path(output_dir) / video_id

    # --- Check cache ---
    cached = _load_cache(cache_dir)
    if cached is not None:
        return cached

    # --- Metadata ---
    info = _get_video_info(video_id)
    title = info.get("title", "")
    duration = float(info.get("duration", 0))
    channel = info.get("channel", info.get("uploader", ""))

    # --- Transcript ---
    transcript_entries, source = extract_transcript(video_id)
    if not transcript_entries:
        raise RuntimeError(
            f"No transcript could be obtained for video {video_id}. "
            "It may be private, age-restricted, or have no audio."
        )

    # --- Chunk (15-second segments for precise timestamp matching) ---
    chunks = chunk_transcript(transcript_entries, chunk_duration=15.0)

    # --- Frames (1 every 5 seconds) ---
    frames_dir = cache_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    segments: list[VideoSegment] = []
    for idx, chunk in enumerate(chunks):
        ts = chunk["start"]
        ts_list: list[float] = []
        while ts < chunk["end"]:
            ts_list.append(ts)
            ts += 5.0

        frame_paths: list[str] = []
        try:
            frame_paths = extract_frames(video_id, ts_list, str(frames_dir))
        except Exception as exc:
            logger.warning("Frame extraction failed for segment %d: %s", idx, exc)

        segments.append(
            VideoSegment(
                video_id=video_id,
                segment_index=idx,
                start_time=chunk["start"],
                end_time=chunk["end"],
                transcript_text=chunk["text"],
                frame_paths=frame_paths,
            )
        )

    metadata = VideoMetadata(
        video_id=video_id,
        title=title,
        duration=duration,
        channel=channel,
        segment_count=len(segments),
        transcript_source=source,
    )

    result = IngestResult(metadata=metadata, segments=segments)

    # --- Persist cache ---
    _save_cache(cache_dir, result)

    logger.info(
        "Ingestion complete: %s — %d segments, source=%s",
        video_id,
        len(segments),
        source,
    )
    return result
