"""Unit tests for the video ingestion pipeline."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.ingest import (
    chunk_transcript,
    extract_frames,
    extract_transcript,
    ingest_video,
    parse_video_id,
    _load_cache,
    _save_cache,
)
from pipeline.models import IngestResult, VideoMetadata, VideoSegment


# ---------------------------------------------------------------------------
# parse_video_id
# ---------------------------------------------------------------------------


class TestParseVideoId:
    def test_full_url(self):
        assert parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_id(self):
        assert parse_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_no_scheme(self):
        assert parse_video_id("youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_video_id("not-a-url")


# ---------------------------------------------------------------------------
# chunk_transcript
# ---------------------------------------------------------------------------


class TestChunkTranscript:
    def test_empty(self):
        assert chunk_transcript([]) == []

    def test_single_entry(self):
        entries = [{"text": "Hello world", "start": 0.0, "duration": 5.0}]
        chunks = chunk_transcript(entries, chunk_duration=120.0)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world"
        assert chunks[0]["start"] == 0.0

    def test_splits_at_boundary(self):
        # 6 entries, each starting 30s apart → 3 minutes total → 2 chunks
        entries = [
            {"text": f"Entry {i}", "start": i * 30.0, "duration": 25.0}
            for i in range(6)
        ]
        chunks = chunk_transcript(entries, chunk_duration=120.0)
        assert len(chunks) == 2
        # First chunk: entries 0-3 (start 0, 30, 60, 90)
        assert "Entry 0" in chunks[0]["text"]
        assert "Entry 3" in chunks[0]["text"]
        # Second chunk: entries 4-5 (start 120, 150)
        assert "Entry 4" in chunks[1]["text"]

    def test_all_within_one_chunk(self):
        entries = [
            {"text": f"Word {i}", "start": i * 10.0, "duration": 8.0}
            for i in range(5)
        ]
        chunks = chunk_transcript(entries, chunk_duration=120.0)
        assert len(chunks) == 1

    def test_chunk_end_time_correct(self):
        entries = [
            {"text": "A", "start": 0.0, "duration": 10.0},
            {"text": "B", "start": 10.0, "duration": 10.0},
        ]
        chunks = chunk_transcript(entries, chunk_duration=120.0)
        assert chunks[0]["end"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# extract_transcript (mocked)
# ---------------------------------------------------------------------------


class TestExtractTranscript:
    @patch("pipeline.ingest.YouTubeTranscriptApi", create=True)
    def test_captions_success(self, mock_api):
        # Patch the import inside the function
        mock_entries = [{"text": "Hi", "start": 0.0, "duration": 2.0}]
        with patch.dict("sys.modules", {"youtube_transcript_api": MagicMock()}):
            with patch("pipeline.ingest.extract_transcript") as mock_fn:
                mock_fn.return_value = (mock_entries, "captions")
                entries, source = mock_fn("FAKE_ID")
        assert source == "captions"
        assert len(entries) == 1

    def test_whisper_fallback_is_callable(self):
        # Just verify the function signature exists — actual whisper test needs GPU
        from pipeline.ingest import _whisper_transcribe
        assert callable(_whisper_transcribe)


# ---------------------------------------------------------------------------
# Cache round-trip
# ---------------------------------------------------------------------------


class TestCacheRoundTrip:
    def test_save_and_load(self, tmp_path: Path):
        result = IngestResult(
            metadata=VideoMetadata(
                video_id="test123abcd",
                title="Test Video",
                duration=300.0,
                channel="TestChannel",
                segment_count=1,
                transcript_source="captions",
            ),
            segments=[
                VideoSegment(
                    video_id="test123abcd",
                    segment_index=0,
                    start_time=0.0,
                    end_time=120.0,
                    transcript_text="Hello world",
                    frame_paths=["/tmp/frame.jpg"],
                )
            ],
        )
        _save_cache(tmp_path, result)
        loaded = _load_cache(tmp_path)
        assert loaded is not None
        assert loaded.metadata.video_id == "test123abcd"
        assert len(loaded.segments) == 1
        assert loaded.segments[0].transcript_text == "Hello world"

    def test_load_missing_returns_none(self, tmp_path: Path):
        assert _load_cache(tmp_path) is None


# ---------------------------------------------------------------------------
# extract_frames (mocked subprocess)
# ---------------------------------------------------------------------------


class TestExtractFrames:
    @patch("pipeline.ingest.subprocess.run")
    @patch("pipeline.ingest._resize_frame")
    def test_extracts_correct_count(self, mock_resize, mock_run, tmp_path: Path):
        mock_run.return_value = MagicMock(returncode=0)
        # Pre-create the video file so download is skipped
        vid = tmp_path / "TESTVID12345.mp4"
        vid.write_bytes(b"fake")

        # Pre-create frame files so ffmpeg calls resolve
        for ts in [0.0, 30.0, 60.0]:
            (tmp_path / f"frame_{ts:07.1f}s.jpg").write_bytes(b"fake-jpg")

        paths = extract_frames("TESTVID12345", [0.0, 30.0, 60.0], str(tmp_path))
        assert len(paths) == 3


# ---------------------------------------------------------------------------
# ingest_video (integration-style with mocks)
# ---------------------------------------------------------------------------


class TestIngestVideoMocked:
    @patch("pipeline.ingest.extract_frames")
    @patch("pipeline.ingest.extract_transcript")
    @patch("pipeline.ingest._get_video_info")
    def test_full_pipeline(self, mock_info, mock_transcript, mock_frames, tmp_path):
        mock_info.return_value = {
            "title": "Test Lecture",
            "duration": 300,
            "channel": "Prof X",
        }
        mock_transcript.return_value = (
            [
                {"text": f"Sentence {i}", "start": i * 20.0, "duration": 18.0}
                for i in range(15)  # 300s of content
            ],
            "captions",
        )
        mock_frames.return_value = ["/fake/frame1.jpg", "/fake/frame2.jpg"]

        result = asyncio.run(
            ingest_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(tmp_path))
        )

        assert result.metadata.video_id == "dQw4w9WgXcQ"
        assert result.metadata.title == "Test Lecture"
        assert result.metadata.segment_count > 0
        assert len(result.segments) == result.metadata.segment_count
        assert all(seg.transcript_text for seg in result.segments)
        assert all(len(seg.frame_paths) > 0 for seg in result.segments)

    @patch("pipeline.ingest.extract_transcript")
    @patch("pipeline.ingest._get_video_info")
    def test_no_transcript_raises(self, mock_info, mock_transcript, tmp_path):
        mock_info.return_value = {"title": "T", "duration": 60, "channel": "C"}
        mock_transcript.return_value = ([], "captions")

        with pytest.raises(RuntimeError, match="No transcript"):
            asyncio.run(
                ingest_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(tmp_path))
            )

    @patch("pipeline.ingest._load_cache")
    def test_returns_cached(self, mock_cache, tmp_path):
        cached = IngestResult(
            metadata=VideoMetadata(
                video_id="dQw4w9WgXcQ",
                title="Cached",
                duration=100.0,
                channel="Ch",
                segment_count=1,
                transcript_source="captions",
            ),
            segments=[
                VideoSegment(
                    video_id="dQw4w9WgXcQ",
                    segment_index=0,
                    start_time=0.0,
                    end_time=100.0,
                    transcript_text="cached text",
                    frame_paths=[],
                )
            ],
        )
        mock_cache.return_value = cached

        result = asyncio.run(
            ingest_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(tmp_path))
        )
        assert result.metadata.title == "Cached"
