"""Tests for SM-2 spaced repetition + checkpoint placement."""
from __future__ import annotations

import pytest

from pipeline.checkpoints import place_checkpoints
from pipeline.spaced_repetition import sm2_update


def test_sm2_correct_increases_interval():
    r, ef, iv = sm2_update(True, 0, 2.5, 1)
    assert r == 1 and iv == 1
    r, ef, iv = sm2_update(True, r, ef, iv)
    assert r == 2 and iv == 6
    r, ef, iv = sm2_update(True, r, ef, iv)
    assert r == 3 and iv >= 15


def test_sm2_wrong_resets():
    r, ef, iv = sm2_update(False, 3, 2.5, 15)
    assert r == 0 and iv == 1


def test_sm2_ease_floor():
    _, ef, _ = sm2_update(False, 0, 1.3, 1)
    assert ef >= 1.3


def test_checkpoint_placement_basic():
    chunks = [
        {
            "chunk_id": f"c{i}",
            "text": f"content about topic {i}",
            "start_time": i * 10,
            "end_time": (i + 1) * 10,
        }
        for i in range(30)
    ]
    cps = place_checkpoints(chunks, 300, target_interval_minutes=2)
    assert len(cps) >= 1
    assert all("timestamp_seconds" in cp for cp in cps)
    assert all("topic_label" in cp for cp in cps)


def test_checkpoint_minimum_spacing():
    chunks = [
        {
            "chunk_id": f"c{i}",
            "text": f"text {i}",
            "start_time": i * 10,
            "end_time": (i + 1) * 10,
        }
        for i in range(60)
    ]
    cps = place_checkpoints(chunks, 600, target_interval_minutes=3)
    for i in range(1, len(cps)):
        gap = cps[i]["timestamp_seconds"] - cps[i - 1]["timestamp_seconds"]
        assert gap >= 180, f"Spacing {gap}s < 180s minimum"


def test_checkpoint_empty_chunks():
    cps = place_checkpoints([], 0)
    assert cps == []


def test_checkpoint_short_video():
    chunks = [{"chunk_id": "c0", "text": "intro", "start_time": 0, "end_time": 10}]
    cps = place_checkpoints(chunks, 10)
    assert cps == []  # too short for checkpoints
