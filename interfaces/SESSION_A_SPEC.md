# Session A: Video Ingestion Worker — Interface Specification

## Status
- **Assigned:** Not yet started
- **Dependencies:** None — can start immediately (parallel with Session B)
- **Last updated:** March 29, 2026

---

## Your Mission
Build the video ingestion pipeline that downloads YouTube videos, extracts transcripts and key frames, and chunks everything into time-aligned segments.

## Context
We're building an AI Teaching Assistant for YouTube lectures (based on the EduVidQA paper, EMNLP 2025). Your module is the FIRST step: when a student provides a YouTube URL + timestamp, you download/process the video so other modules can embed and retrieve from it.

## Hardware
- MacBook Air M2 16GB (local dev)
- HuggingFace Spaces 2-vCPU 16GB (production)

## Files You Create
```
pipeline/ingest.py          # Main ingestion module
pipeline/models.py          # Shared Pydantic data models (used by ALL sessions)
tests/test_ingest.py        # Unit tests
```

## Shared Data Models (YOU define these in pipeline/models.py)

```python
from pydantic import BaseModel
from typing import Optional
import numpy as np

class VideoSegment(BaseModel):
    """A 2-minute chunk of a lecture video with aligned text + frames."""
    video_id: str                    # YouTube video ID (e.g., "dQw4w9WgXcQ")
    segment_index: int               # 0-based index of this chunk
    start_time: float                # Start timestamp in seconds
    end_time: float                  # End timestamp in seconds  
    transcript_text: str             # Transcript text for this segment
    frame_paths: list[str]           # Paths to extracted key frames (JPEGs)
    
    class Config:
        arbitrary_types_allowed = True

class VideoMetadata(BaseModel):
    """Metadata about a processed video."""
    video_id: str
    title: str
    duration: float                  # Total duration in seconds
    channel: str
    segment_count: int
    transcript_source: str           # "captions" or "whisper"
    
class IngestResult(BaseModel):
    """Output of the full ingestion pipeline."""
    metadata: VideoMetadata
    segments: list[VideoSegment]
```

## Functions You Implement

### `pipeline/ingest.py`

```python
async def ingest_video(youtube_url: str, output_dir: str = "./data") -> IngestResult:
    """
    Full pipeline: URL → transcript + frames → chunked segments.
    
    Args:
        youtube_url: Full YouTube URL or video ID
        output_dir: Directory to store frames and cache
        
    Returns:
        IngestResult with metadata + list of VideoSegments
    """
    pass

def extract_transcript(video_id: str) -> tuple[list[dict], str]:
    """
    Get transcript. Try youtube-transcript-api first, fallback to Whisper.
    
    Returns:
        (transcript_entries, source) where entries = [{"text": "...", "start": 0.0, "duration": 5.0}, ...]
        source = "captions" or "whisper"
    """
    pass

def extract_frames(video_id: str, timestamps: list[float], output_dir: str) -> list[str]:
    """
    Extract frames at specific timestamps using yt-dlp + ffmpeg.
    
    Args:
        video_id: YouTube video ID
        timestamps: List of timestamps in seconds to extract frames at
        output_dir: Where to save JPEGs
        
    Returns:
        List of file paths to extracted JPEG frames
    """
    pass

def chunk_transcript(
    transcript_entries: list[dict], 
    chunk_duration: float = 120.0  # 2 minutes
) -> list[dict]:
    """
    Group transcript entries into fixed-duration chunks.
    
    Each chunk: {"start": float, "end": float, "text": str}
    """
    pass
```

## Key Requirements

1. **Transcript extraction**: Use `youtube_transcript_api` first (fast, no download). If no captions, download audio with `yt-dlp` and transcribe with `whisper` (small model).

2. **Frame extraction**: Extract 1 frame every 30 seconds within each 2-minute segment. Use `yt-dlp` to download video (lowest quality, 360p) + `ffmpeg` to extract frames. Save as JPEG, max 512px width.

3. **Chunking**: Split transcript into 2-minute segments. Align frame paths to their corresponding segments. Handle edge cases (transcript gaps, partial segments at end).

4. **Caching**: If `output_dir/{video_id}/` already exists with processed data, skip re-processing and load from cache.

5. **Error handling**: Handle private videos, age-restricted videos, missing transcripts gracefully — return clear error messages.

## Dependencies (pip install)
```
youtube-transcript-api
yt-dlp
ffmpeg-python
Pillow
pydantic
openai-whisper  # fallback only
```

## Test Criteria
```python
# Test with a known public lecture video
result = await ingest_video("https://www.youtube.com/watch?v=VIDEO_ID")

assert result.metadata.video_id == "VIDEO_ID"
assert result.metadata.segment_count > 0
assert len(result.segments) == result.metadata.segment_count
assert all(seg.transcript_text for seg in result.segments)  # No empty transcripts
assert all(len(seg.frame_paths) > 0 for seg in result.segments)  # Each segment has frames
assert all(seg.end_time - seg.start_time <= 130 for seg in result.segments)  # ~2 min chunks
```

## Important Notes
- Keep frame files small (JPEG, 512px max width, quality 80). We'll feed these to Qwen2.5-VL.
- The `VideoSegment` model is shared with Session B (RAG) and Session C (Inference) — don't change the schema without updating this spec.
- For dev/testing, use a SHORT public lecture (~10 min). Don't download hour-long videos during development.

---

## Worker Updates (Session A fills this in)

### Progress Log
<!-- Worker: Add your updates below this line -->

**March 29, 2026 — Session A complete (all tests green)**
- Created `pipeline/models.py` — all shared Pydantic models (VideoSegment, VideoMetadata, IngestResult). Fixed `QualityScores | None` → `Optional[QualityScores]` for Python 3.9 compat.
- Created `pipeline/ingest.py` — full pipeline: `parse_video_id`, `extract_transcript` (captions API + Whisper fallback), `chunk_transcript` (2-min chunks), `extract_frames` (yt-dlp + ffmpeg, 512px JPEG), `ingest_video` (async orchestrator with caching).
- Created `tests/test_ingest.py` — 18 unit tests covering URL parsing, chunking, cache round-trip, frame extraction (mocked), and full pipeline (mocked). All passing.
- Caching implemented: saves `metadata.json` + `segments.json` under `output_dir/{video_id}/`, skips re-processing on subsequent calls.
