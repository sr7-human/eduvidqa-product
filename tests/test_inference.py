"""Unit tests for Session C: Inference + Evaluation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pipeline.models import (
    AnswerResult,
    QualityScores,
    RetrievedContext,
    RetrievalResult,
    VideoSegment,
)
from pipeline.prompts import SYSTEM_PROMPT, build_answer_prompt


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def mock_retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        query="How does backpropagation work?",
        video_id="test123",
        contexts=[
            RetrievedContext(
                segment=VideoSegment(
                    video_id="test123",
                    segment_index=0,
                    start_time=120,
                    end_time=240,
                    transcript_text="Backpropagation works by computing gradients of the loss function with respect to each weight using the chain rule.",
                    frame_paths=["test_frame1.jpg", "test_frame2.jpg"],
                ),
                relevance_score=0.92,
                rank=1,
            ),
            RetrievedContext(
                segment=VideoSegment(
                    video_id="test123",
                    segment_index=1,
                    start_time=240,
                    end_time=360,
                    transcript_text="The gradient is then used to update weights in the opposite direction of the gradient descent.",
                    frame_paths=["test_frame3.jpg"],
                ),
                relevance_score=0.85,
                rank=2,
            ),
        ],
        total_segments=10,
    )


# ── Prompt Tests ──────────────────────────────────────────────────────


class TestBuildAnswerPrompt:
    def test_returns_system_and_user_messages(self, mock_retrieval_result: RetrievalResult):
        messages = build_answer_prompt(
            mock_retrieval_result.query,
            mock_retrieval_result.contexts,
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM_PROMPT
        assert messages[1]["role"] == "user"

    def test_user_content_has_text_and_images(self, mock_retrieval_result: RetrievalResult):
        messages = build_answer_prompt(
            mock_retrieval_result.query,
            mock_retrieval_result.contexts,
        )
        user_content = messages[1]["content"]
        types = {item["type"] for item in user_content}
        assert "text" in types
        assert "image" in types

    def test_respects_max_frames(self):
        """Ensure we never exceed MAX_TOTAL_FRAMES (15)."""
        contexts = [
            RetrievedContext(
                segment=VideoSegment(
                    video_id="v",
                    segment_index=i,
                    start_time=i * 120,
                    end_time=(i + 1) * 120,
                    transcript_text="transcript",
                    frame_paths=[f"f{i}_{j}.jpg" for j in range(10)],
                ),
                relevance_score=0.9,
                rank=i + 1,
            )
            for i in range(10)
        ]
        messages = build_answer_prompt("question?", contexts)
        image_count = sum(
            1 for item in messages[1]["content"] if item["type"] == "image"
        )
        assert image_count <= 15

    def test_question_appears_in_prompt(self, mock_retrieval_result: RetrievalResult):
        messages = build_answer_prompt(
            mock_retrieval_result.query,
            mock_retrieval_result.contexts,
        )
        full_text = " ".join(
            item.get("text", "") for item in messages[1]["content"]
        )
        assert "How does backpropagation work?" in full_text


# ── Model Tests (mocked — no GPU required) ───────────────────────────


class TestAnswerResult:
    def test_answer_result_creation(self):
        result = AnswerResult(
            question="What is gradient descent?",
            answer="Gradient descent is an optimization algorithm...",
            video_id="test123",
            sources=[{"start_time": 120, "end_time": 240, "relevance_score": 0.92}],
            quality_scores=None,
            model_name="Qwen/Qwen2.5-VL-7B-Instruct",
            generation_time_seconds=5.3,
        )
        assert result.model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
        assert result.generation_time_seconds > 0
        assert len(result.sources) == 1

    def test_answer_result_with_scores(self):
        scores = QualityScores(clarity=4.0, ect=3.5, upt=4.0)
        result = AnswerResult(
            question="q",
            answer="a",
            video_id="v",
            sources=[],
            quality_scores=scores,
            model_name="Qwen/Qwen2.5-VL-7B-Instruct",
            generation_time_seconds=1.0,
        )
        assert result.quality_scores is not None
        assert result.quality_scores.clarity == 4.0


# ── Evaluation Tests ─────────────────────────────────────────────────


class TestParseScores:
    def test_parse_valid_json(self):
        from pipeline.evaluate import _parse_scores

        raw = '{"clarity": 4, "ect": 3, "upt": 5}'
        scores = _parse_scores(raw)
        assert scores["clarity"] == 4.0
        assert scores["ect"] == 3.0
        assert scores["upt"] == 5.0

    def test_parse_json_in_text(self):
        from pipeline.evaluate import _parse_scores

        raw = 'Here are the scores: {"clarity": 3.5, "ect": 2, "upt": 4} Done.'
        scores = _parse_scores(raw)
        assert scores["clarity"] == 3.5

    def test_parse_invalid_raises(self):
        from pipeline.evaluate import _parse_scores

        with pytest.raises(ValueError, match="Could not parse"):
            _parse_scores("no scores here")


class TestQualityScoresValidation:
    def test_score_out_of_range_raises(self):
        with pytest.raises(Exception):
            QualityScores(clarity=6, ect=3, upt=2)

    def test_score_below_range_raises(self):
        with pytest.raises(Exception):
            QualityScores(clarity=0, ect=3, upt=2)
