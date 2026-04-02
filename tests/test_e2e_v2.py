"""E2E test v2: test full pipeline against the 3 pre-indexed videos.

Run with backend up:
    cd /Users/shubhamkumar/eduvidqa-product
    .venv/bin/uvicorn backend.app:app --reload

Then:
    .venv/bin/python -m pytest tests/test_e2e_v2.py -v
"""

from __future__ import annotations

import os
import sys

import httpx
import pytest

BASE_URL = os.getenv("API_URL", "http://localhost:8000")

# Pre-indexed test videos
VIDEOS = [
    {
        "id": "3OmfTIf-SOU",
        "url": "https://www.youtube.com/watch?v=3OmfTIf-SOU",
        "title_contains": "unit test",
        "questions": [
            {"q": "What is unit testing?", "ts": 30.0},
            {"q": "What does the get_route_score function do?", "ts": 120.0},
        ],
    },
    {
        "id": "VRcixOuG-TU",
        "url": "https://www.youtube.com/watch?v=VRcixOuG-TU",
        "title_contains": "perceptron",
        "questions": [
            {"q": "How does a perceptron work?", "ts": 60.0},
            {"q": "What is the activation function?", "ts": 300.0},
        ],
    },
    {
        "id": "oZgbwa8lvDE",
        "url": "https://www.youtube.com/watch?v=oZgbwa8lvDE",
        "title_contains": "insertion sort",
        "questions": [
            {"q": "How does insertion sort work?", "ts": 120.0},
            {"q": "What is the time complexity of insertion sort?", "ts": 600.0},
        ],
    },
]


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=120)


# ── Health ────────────────────────────────────────────────────────────


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


# ── Process Video (already indexed — should be fast) ──────────────────


@pytest.mark.parametrize("video", VIDEOS, ids=[v["id"] for v in VIDEOS])
def test_process_video(client, video):
    r = client.post("/api/process-video", json={"youtube_url": video["url"]})
    assert r.status_code == 200
    data = r.json()
    assert data["video_id"] == video["id"]


# ── Ask Questions ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "video,qidx",
    [(v, i) for v in VIDEOS for i in range(len(v["questions"]))],
    ids=[f"{v['id']}_q{i}" for v in VIDEOS for i in range(len(v["questions"]))],
)
def test_ask_question(client, video, qidx):
    q = video["questions"][qidx]
    r = client.post(
        "/api/ask",
        json={
            "youtube_url": video["url"],
            "question": q["q"],
            "timestamp": q["ts"],
            "skip_quality_eval": True,  # skip scoring to speed up tests
        },
    )
    assert r.status_code == 200
    data = r.json()

    # Answer should be non-trivial
    assert len(data["answer"]) > 50, f"Answer too short: {data['answer'][:100]}"

    # Should have sources
    assert len(data["sources"]) > 0

    # Sources should have valid structure
    for src in data["sources"]:
        assert "start_time" in src
        assert "end_time" in src
        assert "relevance_score" in src

    # Model name should be set
    assert data["model_name"]


# ── Ask with Quality Scoring ─────────────────────────────────────────


def test_ask_with_scoring(client):
    """Test one question with quality scoring enabled."""
    r = client.post(
        "/api/ask",
        json={
            "youtube_url": VIDEOS[0]["url"],
            "question": VIDEOS[0]["questions"][0]["q"],
            "timestamp": VIDEOS[0]["questions"][0]["ts"],
            "skip_quality_eval": False,
        },
    )
    assert r.status_code == 200
    data = r.json()

    assert len(data["answer"]) > 50
    assert data["quality_scores"] is not None
    assert 1 <= data["quality_scores"]["clarity"] <= 5
    assert 1 <= data["quality_scores"]["ect"] <= 5
    assert 1 <= data["quality_scores"]["upt"] <= 5


# ── Error Cases ───────────────────────────────────────────────────────


def test_ask_empty_question(client):
    r = client.post(
        "/api/ask",
        json={
            "youtube_url": VIDEOS[0]["url"],
            "question": "",
            "timestamp": 0,
        },
    )
    assert r.status_code == 422  # Validation error


def test_process_invalid_url(client):
    r = client.post(
        "/api/process-video",
        json={"youtube_url": "not-a-url"},
    )
    assert r.status_code in (400, 422)
