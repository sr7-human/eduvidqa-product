"""Unit tests for the RAG pipeline (Session B)."""

import shutil
import tempfile

import pytest

from pipeline.models import VideoSegment
from pipeline.rag import LectureIndex, _subchunk


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def tmp_chroma(tmp_path):
    """Provide a temporary directory for ChromaDB storage."""
    return str(tmp_path / "chroma")


@pytest.fixture()
def sample_segments() -> list[VideoSegment]:
    """Return a small set of realistic lecture segments."""
    return [
        VideoSegment(
            video_id="test123",
            segment_index=0,
            start_time=0,
            end_time=120,
            transcript_text=(
                "Today we'll discuss backpropagation in neural networks. "
                "Backpropagation is the backbone of training deep learning models. "
                "It uses the chain rule of calculus to compute gradients layer by layer."
            ),
            frame_paths=["frame_0.jpg"],
        ),
        VideoSegment(
            video_id="test123",
            segment_index=1,
            start_time=120,
            end_time=240,
            transcript_text=(
                "Gradient descent works by computing partial derivatives of the loss "
                "function with respect to each weight. We then update each weight by "
                "subtracting a fraction of the gradient, controlled by the learning rate."
            ),
            frame_paths=["frame_1.jpg"],
        ),
        VideoSegment(
            video_id="test123",
            segment_index=2,
            start_time=240,
            end_time=360,
            transcript_text=(
                "Convolutional neural networks apply filters across spatial dimensions. "
                "The convolution operation detects local features like edges and textures. "
                "Pooling layers reduce spatial resolution while keeping important signals."
            ),
            frame_paths=["frame_2.jpg"],
        ),
        VideoSegment(
            video_id="test123",
            segment_index=3,
            start_time=360,
            end_time=480,
            transcript_text=(
                "Recurrent neural networks process sequential data. LSTMs introduce "
                "gates — input, forget, and output gates — to handle long-term dependencies. "
                "Transformers replaced RNNs by using self-attention mechanisms."
            ),
            frame_paths=["frame_3.jpg"],
        ),
    ]


# ── Sub-chunking ──────────────────────────────────────────────────


class TestSubchunk:
    def test_short_text_not_split(self):
        text = "This is short."
        chunks = _subchunk(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_split(self):
        sentences = ["Sentence number %d is here." % i for i in range(200)]
        text = " ".join(sentences)
        chunks = _subchunk(text)
        assert len(chunks) > 1
        # Each chunk should be ≤ 500 words (roughly)
        for c in chunks:
            assert len(c.split()) <= 600  # allow slight overshoot from overlap

    def test_empty_text(self):
        assert _subchunk("") == [""]


# ── Indexing ──────────────────────────────────────────────────────


class TestLectureIndex:
    def test_index_and_is_indexed(self, tmp_chroma, sample_segments):
        index = LectureIndex(persist_dir=tmp_chroma)
        count = index.index_segments(sample_segments)

        assert count == len(sample_segments)
        assert index.is_indexed("test123")
        assert not index.is_indexed("nonexistent")

    def test_index_empty(self, tmp_chroma):
        index = LectureIndex(persist_dir=tmp_chroma)
        assert index.index_segments([]) == 0

    def test_re_index_overwrites(self, tmp_chroma, sample_segments):
        """Re-indexing the same video should cleanly replace old data."""
        index = LectureIndex(persist_dir=tmp_chroma)
        index.index_segments(sample_segments)
        # Index again with fewer segments
        count = index.index_segments(sample_segments[:2])
        assert count == 2
        assert index.is_indexed("test123")

    # ── Retrieval ─────────────────────────────────────────────────

    def test_retrieve_relevant(self, tmp_chroma, sample_segments):
        index = LectureIndex(persist_dir=tmp_chroma)
        index.index_segments(sample_segments)

        result = index.retrieve(
            "How does backpropagation work?", video_id="test123", top_k=3
        )

        assert len(result.contexts) <= 3
        assert result.query == "How does backpropagation work?"
        assert result.video_id == "test123"
        assert result.total_segments > 0

        # Top result should mention backpropagation
        top = result.contexts[0]
        assert "backpropagation" in top.segment.transcript_text.lower()

        # Results are sorted by descending relevance
        scores = [c.relevance_score for c in result.contexts]
        assert scores == sorted(scores, reverse=True)

        # Ranks are 1-based
        ranks = [c.rank for c in result.contexts]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_retrieve_cnn_query(self, tmp_chroma, sample_segments):
        index = LectureIndex(persist_dir=tmp_chroma)
        index.index_segments(sample_segments)

        result = index.retrieve(
            "What are convolutional neural networks?", video_id="test123", top_k=2
        )
        assert len(result.contexts) <= 2
        top_text = result.contexts[0].segment.transcript_text.lower()
        assert "convolutional" in top_text or "convolution" in top_text

    def test_retrieve_not_indexed_raises(self, tmp_chroma):
        index = LectureIndex(persist_dir=tmp_chroma)
        with pytest.raises(ValueError, match="not been indexed"):
            index.retrieve("anything", video_id="no_such_video")

    # ── Deletion ──────────────────────────────────────────────────

    def test_delete_video(self, tmp_chroma, sample_segments):
        index = LectureIndex(persist_dir=tmp_chroma)
        index.index_segments(sample_segments)

        assert index.delete_video("test123") is True
        assert not index.is_indexed("test123")
        assert index.delete_video("test123") is False  # already gone

    # ── Frame paths round-trip ────────────────────────────────────

    def test_frame_paths_preserved(self, tmp_chroma, sample_segments):
        index = LectureIndex(persist_dir=tmp_chroma)
        index.index_segments(sample_segments)

        result = index.retrieve("backpropagation", video_id="test123", top_k=1)
        seg = result.contexts[0].segment
        assert seg.frame_paths == ["frame_0.jpg"]
