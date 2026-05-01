"""Verify API response shapes match expected contracts.

Requires a running backend at http://localhost:8000.
Skipped automatically if unreachable.
"""
import httpx
import pytest

BASE = "http://localhost:8000"


def _backend_up() -> bool:
    try:
        return httpx.get(f"{BASE}/api/health", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _backend_up(), reason="backend not running on :8000")


def test_health_shape():
    r = httpx.get(f"{BASE}/api/health")
    assert r.status_code == 200
    d = r.json()
    assert "status" in d and "model_name" in d


def test_ask_requires_auth_for_non_demo():
    r = httpx.post(
        f"{BASE}/api/ask",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=VRcixOuG-TU",
            "question": "test",
            "timestamp": 0,
        },
    )
    assert r.status_code == 401


def test_ask_demo_no_auth():
    r = httpx.post(
        f"{BASE}/api/ask",
        json={
            "youtube_url": "https://www.youtube.com/watch?v=3OmfTIf-SOU",
            "question": "What is unit testing?",
            "timestamp": 60,
            "skip_quality_eval": True,
        },
        timeout=60.0,
    )
    # 200 if indexed, 202 if processing — both acceptable
    assert r.status_code in (200, 202)


def test_video_status():
    r = httpx.get(f"{BASE}/api/videos/3OmfTIf-SOU/status")
    assert r.status_code == 200
    assert r.json()["status"] in ("ready", "processing", "pending")


def test_unknown_video_404():
    r = httpx.get(f"{BASE}/api/videos/XXXXXXXXXXX/status")
    assert r.status_code == 404
