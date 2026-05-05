"""Global quiz cache: (video_id, ts_bucket_30s, prompt_version) -> questions."""
from __future__ import annotations

import json
import logging
import os
import uuid

import psycopg2

logger = logging.getLogger(__name__)


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL env var not set")
    return url


def _coerce_options(opts) -> list:
    if isinstance(opts, list):
        return opts
    if isinstance(opts, str):
        try:
            return json.loads(opts)
        except json.JSONDecodeError:
            return [opts]
    return list(opts) if opts else []


def get_cached_questions(
    video_id: str, ts_bucket: int, prompt_version: int = 1
) -> list[dict] | None:
    """Return cached questions or None on cache miss."""
    conn = psycopg2.connect(_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, question_text, options, correct_answer, explanation, difficulty, bloom_level
                FROM questions
                WHERE video_id = %s AND ts_bucket_30s = %s AND prompt_version = %s
                ORDER BY
                    CASE bloom_level
                        WHEN 'remember'   THEN 1
                        WHEN 'understand' THEN 2
                        WHEN 'apply'      THEN 3
                        WHEN 'analyse'    THEN 4
                        WHEN 'evaluate'   THEN 5
                        ELSE 6
                    END,
                    question_text
                """,
                (video_id, ts_bucket, prompt_version),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return None
    return [
        {
            "id": str(r[0]),
            "question_text": r[1],
            "options": _coerce_options(r[2]),
            "correct_answer": r[3],
            "explanation": r[4],
            "difficulty": r[5],
            "bloom_level": r[6] if len(r) > 6 else "understand",
        }
        for r in rows
    ]


def cache_questions(
    video_id: str,
    ts_bucket: int,
    prompt_version: int,
    questions: list[dict],
) -> None:
    """Insert generated questions into the global cache (idempotent)."""
    if not questions:
        return
    conn = psycopg2.connect(_db_url())
    try:
        with conn.cursor() as cur:
            for q in questions:
                cur.execute(
                    """
                    INSERT INTO questions (
                        id, video_id, ts_bucket_30s, prompt_version,
                        question_text, options, correct_answer, explanation,
                        difficulty, bloom_level
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (video_id, ts_bucket_30s, prompt_version, question_text)
                    DO NOTHING
                    """,
                    (
                        str(uuid.uuid4()),
                        video_id,
                        ts_bucket,
                        prompt_version,
                        q["question_text"],
                        json.dumps(q.get("options", [])),
                        q.get("correct_answer", "A"),
                        q.get("explanation", ""),
                        q.get("difficulty", "medium"),
                        q.get("bloom_level", "understand"),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def _find_nearest_cached(video_id: str, ts_bucket: int, prompt_version: int = 1) -> list[dict] | None:
    """Find questions from the nearest cached bucket for this video."""
    conn = psycopg2.connect(_db_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ts_bucket_30s
                FROM questions
                WHERE video_id = %s AND prompt_version = %s
                ORDER BY abs(ts_bucket_30s - %s)
                LIMIT 1
                """,
                (video_id, prompt_version, ts_bucket),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    nearest_bucket = row[0]
    logger.info(
        "Nearest cached bucket for %s: requested=%d, found=%d (delta=%ds)",
        video_id, ts_bucket, nearest_bucket, abs(nearest_bucket - ts_bucket) * 30,
    )
    return get_cached_questions(video_id, nearest_bucket, prompt_version)


def get_or_generate(
    video_id: str,
    timestamp: float,
    chunks: list[dict],
    prompt_version: int = 1,
) -> list[dict]:
    """Cache check -> nearest bucket fallback -> generate only if nothing cached."""
    ts_bucket = int(timestamp // 30)

    # 1. Exact bucket match
    cached = get_cached_questions(video_id, ts_bucket, prompt_version)
    if cached:
        logger.info("Quiz cache HIT: %s@bucket%s", video_id, ts_bucket)
        return cached

    # 2. Find nearest cached bucket (no LLM call)
    nearest = _find_nearest_cached(video_id, ts_bucket, prompt_version)
    if nearest:
        logger.info("Quiz cache NEAREST HIT: %s@bucket%s → serving %d questions", video_id, ts_bucket, len(nearest))
        return nearest

    # 3. Nothing cached at all for this video → generate (first time only)
    logger.info("Quiz cache MISS (no questions for video): %s@bucket%s — generating", video_id, ts_bucket)
    from pipeline.quiz_gen import generate_quiz_questions

    questions = generate_quiz_questions(video_id, timestamp, chunks)
    if not questions:
        return []

    cache_questions(video_id, ts_bucket, prompt_version, questions)
    refreshed = get_cached_questions(video_id, ts_bucket, prompt_version)
    return refreshed if refreshed else questions
