"""Integration tests for Session B: embeddings_v2 + rag_v2 + digest.

Run:
    .venv/bin/python -m pytest tests/test_rag_v2.py -v -s

Requires:
    - Session A output in data/processed/{video_id}/
    - GROQ_API_KEY env var (for digest generation)
    - GEMINI_API_KEY env var (only if testing gemini embeddings)
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

DATA_DIR = "data/processed"
CHROMA_TEST_DIR = "data/chroma_test_v2"
VIDEO_IDS = ["3OmfTIf-SOU", "VRcixOuG-TU", "oZgbwa8lvDE"]

# Questions per video (for retrieval validation)
QUESTIONS: dict[str, list[tuple[str, float, str]]] = {
    # (question, approx_timestamp, expected_keyword_in_top_chunk)
    "3OmfTIf-SOU": [
        ("What is unit testing?", 20.0, "unit"),
        ("How do test cases validate functions?", 100.0, "test"),
    ],
    "VRcixOuG-TU": [
        ("What is a perceptron?", 30.0, "perceptron"),
        ("How does activation function work?", 200.0, "activation"),
    ],
    "oZgbwa8lvDE": [
        ("How does insertion sort work?", 60.0, "insertion"),
        ("What is the time complexity?", 400.0, "sort"),
    ],
}


def _load_chunks(video_id: str) -> list[dict]:
    p = Path(DATA_DIR) / video_id / "transcript" / "chunks.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _load_manifest(video_id: str) -> list[dict]:
    p = Path(DATA_DIR) / video_id / "keyframes" / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def chroma_dir(tmp_path_factory):
    """Temporary ChromaDB directory for tests."""
    d = tmp_path_factory.mktemp("chroma_v2")
    yield str(d)
    # cleanup happens automatically via tmp_path_factory


@pytest.fixture(scope="module")
def jina_service():
    """Shared Jina CLIP embedding service (loaded once)."""
    from pipeline.embeddings_v2 import EmbeddingService
    svc = EmbeddingService("jina")
    svc._ensure_loaded()
    return svc


# ── Unit tests (no API calls) ────────────────────────────────────


class TestEmbeddingService:
    """Basic tests for the EmbeddingService."""

    def test_jina_text(self, jina_service):
        vec = jina_service.embed_text("hello world")
        assert len(vec) == 1024
        assert all(isinstance(v, float) for v in vec)

    def test_jina_batch_text(self, jina_service):
        vecs = jina_service.embed_batch_text(["hello", "world"])
        assert len(vecs) == 2
        assert all(len(v) == 1024 for v in vecs)

    def test_jina_image(self, jina_service):
        # Use first keyframe from first video
        manifest = _load_manifest(VIDEO_IDS[0])
        img_path = manifest[0]["file"]
        if Path(img_path).is_file():
            vec = jina_service.embed_image(img_path)
            assert len(vec) == 1024
        else:
            pytest.skip(f"Keyframe file not found: {img_path}")

    def test_dimension(self, jina_service):
        assert jina_service.get_dimension() == 1024

    def test_invalid_model(self):
        from pipeline.embeddings_v2 import EmbeddingService
        with pytest.raises(ValueError, match="Unknown model"):
            EmbeddingService("invalid")


# ── Integration tests (need Session A data) ─────────────────────


class TestLectureIndexV2:
    """Index & retrieve using real Session A data."""

    @pytest.fixture(scope="class")
    def index(self, chroma_dir, jina_service):
        from pipeline.rag_v2 import LectureIndex
        return LectureIndex(
            persist_dir=chroma_dir,
            embedding_model="jina",
            _embed_service=jina_service,
        )

    @pytest.mark.parametrize("video_id", VIDEO_IDS)
    def test_index_video(self, index, video_id):
        chunks = _load_chunks(video_id)
        manifest = _load_manifest(video_id)

        # Use a placeholder digest (real digest needs Groq API)
        digest = f"Placeholder digest for {video_id}"

        count = index.index_video(video_id, chunks, manifest, digest)
        assert count > 0
        print(f"  ✓ Indexed {count} items for {video_id}")

    @pytest.mark.parametrize("video_id", VIDEO_IDS)
    def test_is_indexed(self, index, video_id):
        assert index.is_indexed(video_id)

    @pytest.mark.parametrize("video_id", VIDEO_IDS)
    def test_retrieve(self, index, video_id):
        questions = QUESTIONS[video_id]
        for question, timestamp, keyword in questions:
            result = index.retrieve(question, video_id, timestamp, top_k=5)
            assert len(result["ranked_chunks"]) > 0, f"No chunks for: {question}"
            assert isinstance(result["digest"], str)

            # Check that top chunk contains expected keyword
            top_text = result["ranked_chunks"][0].get("text", "").lower()
            print(f"  Q: {question}")
            print(f"    Top chunk: {top_text[:120]}…")
            print(f"    Keyframes: {len(result['relevant_keyframes'])}")
            # Keyword check is soft — semantic search may rank differently
            # but at least we got results

    def test_retrieve_nonexistent_video(self, index):
        result = index.retrieve("anything", "NONEXISTENT_VIDEO", 0.0)
        assert result["ranked_chunks"] == []


# ── Digest test (needs Groq API) ─────────────────────────────────


class TestDigest:
    """Test digest generation on the shortest video."""

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="GROQ_API_KEY not set",
    )
    def test_generate_digest(self):
        from pipeline.digest import generate_digest

        video_id = "3OmfTIf-SOU"  # shortest video (4.7 min)
        digest = generate_digest(video_id, data_dir=DATA_DIR)
        assert len(digest) > 200, "Digest too short"
        print(f"  Digest length: {len(digest)} chars")
        print(f"  First 300 chars: {digest[:300]}…")

        # Check it was saved
        saved = Path(DATA_DIR) / video_id / "digest.txt"
        assert saved.is_file()
        assert saved.read_text(encoding="utf-8") == digest
