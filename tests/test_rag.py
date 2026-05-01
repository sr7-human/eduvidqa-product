"""Integration tests for pipeline.rag (Supabase pgvector backend).

Run:
    .venv/bin/python -m pytest tests/test_rag.py -v -s

Requires:
    - DATABASE_URL set in .env (Supabase pooler connection string)
    - Jina CLIP v2 cached locally (downloaded on first run)
    - Optional: Session A output in data/processed/{video_id}/ for
      file-based integration tests (skipped if missing).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(override=True)

import psycopg2  # noqa: E402

DATA_DIR = "data/processed"


# ── Helpers ──────────────────────────────────────────────────────


def _cleanup(video_id: str) -> None:
    """Delete all rows for this video_id across the three tables."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM video_chunks WHERE video_id=%s", (video_id,))
        cur.execute("DELETE FROM keyframe_embeddings WHERE video_id=%s", (video_id,))
        cur.execute("DELETE FROM videos WHERE video_id=%s", (video_id,))


def _row_counts(video_id: str) -> dict[str, int]:
    dsn = os.getenv("DATABASE_URL")
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM videos WHERE video_id=%s", (video_id,))
        v = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM video_chunks WHERE video_id=%s", (video_id,))
        c = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM keyframe_embeddings WHERE video_id=%s", (video_id,)
        )
        k = cur.fetchone()[0]
    return {"videos": v, "chunks": c, "keyframes": k}


def _short_vid(prefix: str = "tst") -> str:
    """Generate an 11-char test video_id (matches videos.video_id VARCHAR(11))."""
    return (prefix + uuid.uuid4().hex)[:11]


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def jina_service():
    # Despite the legacy name, this now returns a Gemini-backed EmbeddingService.
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    from pipeline.embeddings import EmbeddingService

    svc = EmbeddingService()
    svc._ensure_loaded()
    return svc


@pytest.fixture
def index(jina_service):
    from pipeline.rag import LectureIndex

    return LectureIndex(_embed_service=jina_service)


# ── Basic interface tests ────────────────────────────────────────


def test_persist_dir_kwarg_is_accepted(jina_service):
    """Backward-compat: persist_dir kwarg must not raise."""
    from pipeline.rag import LectureIndex

    LectureIndex(persist_dir="/tmp/ignored", _embed_service=jina_service)


def test_is_indexed_unknown_returns_false(index):
    assert index.is_indexed("ZZZZZZZZZZZ") is False


# ── Index + retrieve round-trip ──────────────────────────────────


def test_index_video_inserts_rows(index):
    vid = _short_vid()
    chunks = [
        {
            "chunk_id": "tc0",
            "start_time": 0.0,
            "end_time": 10.0,
            "text": "Unit testing verifies individual functions in isolation.",
            "linked_keyframe_ids": [],
        },
        {
            "chunk_id": "tc1",
            "start_time": 10.0,
            "end_time": 20.0,
            "text": "Integration testing checks how modules interact together.",
            "linked_keyframe_ids": [],
        },
    ]
    try:
        total = index.index_video(vid, chunks, [], "Testing lecture digest")
        assert total == 2
        assert index.is_indexed(vid) is True
        counts = _row_counts(vid)
        assert counts == {"videos": 1, "chunks": 2, "keyframes": 0}
    finally:
        _cleanup(vid)


def test_retrieve_returns_relevant_chunks(index):
    vid = _short_vid()
    chunks = [
        {
            "chunk_id": "rc0",
            "start_time": 0.0,
            "end_time": 10.0,
            "text": "Gradient descent moves parameters downhill on the loss surface.",
            "linked_keyframe_ids": [],
        },
        {
            "chunk_id": "rc1",
            "start_time": 10.0,
            "end_time": 20.0,
            "text": "The learning rate controls step size in gradient descent.",
            "linked_keyframe_ids": [],
        },
        {
            "chunk_id": "rc2",
            "start_time": 50.0,
            "end_time": 60.0,
            "text": "Convolution applies a filter sliding across the input image.",
            "linked_keyframe_ids": [],
        },
    ]
    try:
        index.index_video(vid, chunks, [], "ML lecture digest body")
        result = index.retrieve(
            "What is gradient descent?", vid, timestamp=5.0, top_k=2
        )
        assert isinstance(result, dict)
        assert "ranked_chunks" in result
        assert "relevant_keyframes" in result
        assert "digest" in result
        assert len(result["ranked_chunks"]) == 2
        top = result["ranked_chunks"][0]
        assert "relevance_score" in top
        assert "gradient" in top["text"].lower()
        assert result["digest"].startswith("ML lecture")
    finally:
        _cleanup(vid)


def test_retrieve_temporal_reranking(index):
    """Two chunks with similar semantic match — the temporally closer
    one should outrank the far one when timestamp targets it."""
    vid = _short_vid()
    chunks = [
        {
            "chunk_id": "n0",
            "start_time": 0.0,
            "end_time": 10.0,
            "text": "Backpropagation computes gradients via the chain rule.",
            "linked_keyframe_ids": [],
        },
        {
            "chunk_id": "n1",
            "start_time": 500.0,
            "end_time": 510.0,
            "text": "Backpropagation computes gradients via the chain rule.",
            "linked_keyframe_ids": [],
        },
    ]
    try:
        index.index_video(vid, chunks, [], "")
        result = index.retrieve(
            "How does backpropagation work?", vid, timestamp=505.0, top_k=2
        )
        rc = result["ranked_chunks"]
        assert len(rc) == 2
        # Chunk near timestamp=505 (n1) should rank above the far one (n0).
        assert rc[0]["chunk_id"] == "n1"
    finally:
        _cleanup(vid)


def test_retrieve_unknown_video_returns_empty(index):
    result = index.retrieve("anything", "AAAAAAAAAAA", timestamp=0.0)
    assert result["ranked_chunks"] == []
    assert result["relevant_keyframes"] == []
    assert result["digest"] == ""


# ── Optional: real video data (skipped if absent) ────────────────


def _have_video(video_id: str) -> bool:
    p = Path(DATA_DIR) / video_id / "transcript" / "chunks.json"
    return p.is_file()


@pytest.mark.skipif(
    not _have_video("3OmfTIf-SOU"),
    reason="Session A data missing for 3OmfTIf-SOU",
)
def test_index_real_video_chunks(index):
    video_id = "3OmfTIf-SOU"
    test_vid = _short_vid("rv")
    chunks = json.loads(
        (Path(DATA_DIR) / video_id / "transcript" / "chunks.json").read_text()
    )
    try:
        total = index.index_video(test_vid, chunks, [], f"digest for {video_id}")
        assert total == len(chunks)
        result = index.retrieve("what is unit testing", test_vid, 20.0, top_k=3)
        assert len(result["ranked_chunks"]) > 0
    finally:
        _cleanup(test_vid)
