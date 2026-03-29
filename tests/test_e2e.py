"""End-to-end integration tests for the EduVidQA API."""

from __future__ import annotations

import os

import httpx
import pytest

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:7860")
# Use a short public video for testing — update as needed
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=180) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────


def test_health(client: httpx.Client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "model_loaded" in data
    assert "gpu_available" in data


# ── Process video ────────────────────────────────────────────────


def test_process_video(client: httpx.Client):
    r = client.post(
        "/api/process-video",
        json={"youtube_url": TEST_VIDEO_URL},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["video_id"]
    assert data["segment_count"] >= 0  # 0 if cached


def test_process_video_invalid_url(client: httpx.Client):
    r = client.post(
        "/api/process-video",
        json={"youtube_url": "not-a-valid-url"},
    )
    assert r.status_code == 400


# ── Ask question ─────────────────────────────────────────────────


def test_ask_question(client: httpx.Client):
    r = client.post(
        "/api/ask",
        json={
            "youtube_url": TEST_VIDEO_URL,
            "timestamp": 60,
            "question": "What concept is being explained here?",
            "skip_quality_eval": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["answer"]) > 20
    assert data["video_id"]
    assert len(data["sources"]) > 0
    assert data["model_name"]
    assert data["generation_time_seconds"] > 0


def test_ask_question_invalid_url(client: httpx.Client):
    r = client.post(
        "/api/ask",
        json={
            "youtube_url": "invalid",
            "timestamp": 0,
            "question": "What is this?",
        },
    )
    assert r.status_code == 400


def test_ask_question_empty_question(client: httpx.Client):
    r = client.post(
        "/api/ask",
        json={
            "youtube_url": TEST_VIDEO_URL,
            "timestamp": 0,
            "question": "",
        },
    )
    assert r.status_code == 422  # Pydantic validation error
