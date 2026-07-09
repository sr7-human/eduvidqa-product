"""Chapter segmentation + chapter-based quiz generation (prompt_version=2).

This wires up the pedagogical quiz system that was previously implemented in
``quiz_gen.generate_chapter_quizzes`` but never called:

- **pretest**   — fires at a chapter START. Primes the learner ("what's ahead"),
  activates prior knowledge, reduces intrinsic cognitive load.
- **mid_recall** — fires mid-chapter. Locks in the concept just watched.
- **end_recall** — fires at chapter END. Synthesises the whole chapter.

``build_chapters_and_quizzes`` is called from the ingest pipeline (and can be
run standalone to backfill existing videos).
"""
from __future__ import annotations

import json
import logging
import os
import uuid

import psycopg2

from pipeline.quiz_gen import (
    _compute_chapter_count,
    _compute_mid_recall_count,
    generate_chapter_quizzes,
)

logger = logging.getLogger(__name__)

CHAPTER_PROMPT_VERSION = 2


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL env var not set")
    return url


def _title_segments(segments: list[dict], chunks: list[dict]) -> list[str]:
    """One LLM call to title all chapter segments from their transcript.

    Falls back to generic "Part N" titles if the LLM is unavailable/fails.
    """
    from pipeline.quiz_gen import _assemble_context, _call_gemini, _call_llm_backoff, _call_openrouter

    blocks = []
    for i, seg in enumerate(segments, 1):
        seg_chunks = [
            c for c in chunks
            if seg["start_time"] <= float(c.get("start_time", 0)) < seg["end_time"]
        ]
        text = _assemble_context(seg_chunks)[:1000]
        blocks.append(f"--- Segment {i} ({seg['start_time']:.0f}-{seg['end_time']:.0f}s) ---\n{text}")

    prompt = (
        "You are segmenting an educational video into chapters. For each segment "
        "below, write a SHORT, specific chapter title (3-7 words) that captures its "
        "core topic. Do not include the word 'segment' or numbers.\n\n"
        + "\n\n".join(blocks)
        + f"\n\nReturn ONLY a JSON array of exactly {len(segments)} title strings, "
        'in order, e.g. ["Intro to X", "How Y works", ...].'
    )

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    or_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    raw = ""
    try:
        if gemini_key:
            raw = _call_llm_backoff(_call_gemini, prompt, gemini_key, 2000)
        elif or_key:
            raw = _call_llm_backoff(_call_openrouter, prompt, or_key, 2000)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chapter titling failed: %s", str(exc)[:120])

    titles: list[str] = []
    if raw:
        try:
            import re
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                titles = [str(t).strip() for t in parsed if str(t).strip()]
        except Exception:  # noqa: BLE001
            titles = []

    # Pad / fall back to generic titles
    out = []
    for i in range(len(segments)):
        out.append(titles[i] if i < len(titles) else f"Part {i + 1}")
    return out


def segment_chapters(video_id: str, chunks: list[dict], duration_s: float) -> list[dict]:
    """Split a video into evenly-timed, LLM-titled chapters.

    Returns a list of {idx, start_time, end_time, title} (no DB writes).
    """
    if not chunks or duration_s <= 0:
        return []
    n = _compute_chapter_count(duration_s / 60.0)
    span = duration_s / n
    segments = []
    for i in range(n):
        start = i * span
        end = duration_s if i == n - 1 else (i + 1) * span
        segments.append({"idx": i, "start_time": start, "end_time": end})

    titles = _title_segments(segments, chunks)
    for seg, title in zip(segments, titles):
        seg["title"] = title
    return segments


def _persist_chapters(video_id: str, segments: list[dict]) -> list[dict]:
    """Insert chapters (idempotent per video) and return them with DB ids."""
    conn = psycopg2.connect(_db_url())
    conn.autocommit = True
    out: list[dict] = []
    try:
        with conn.cursor() as cur:
            # Clear any prior auto chapters so re-runs don't duplicate.
            cur.execute("DELETE FROM chapters WHERE video_id = %s AND source = 'auto'", (video_id,))
            for seg in segments:
                ch_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO chapters (id, video_id, idx, start_time, end_time, title, source)
                    VALUES (%s, %s, %s, %s, %s, %s, 'auto')
                    """,
                    (ch_id, video_id, seg["idx"], seg["start_time"], seg["end_time"], seg["title"]),
                )
                out.append({**seg, "id": ch_id})
    finally:
        conn.close()
    return out


def _insert_chapter_questions(video_id: str, questions: list[dict], ts_bucket: int) -> int:
    """Insert prompt_version=2 chapter questions. Returns count inserted."""
    if not questions:
        return 0
    conn = psycopg2.connect(_db_url())
    conn.autocommit = True
    n = 0
    try:
        with conn.cursor() as cur:
            for q in questions:
                cur.execute(
                    """
                    INSERT INTO questions (
                        id, video_id, chapter_id, ts_bucket_30s, prompt_version,
                        question_text, options, correct_answer, explanation,
                        difficulty, bloom_level, quiz_type, order_idx, option_explanations
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (video_id, ts_bucket_30s, prompt_version, question_text) DO NOTHING
                    """,
                    (
                        str(uuid.uuid4()), video_id, q.get("chapter_id"), ts_bucket,
                        CHAPTER_PROMPT_VERSION, q["question_text"], json.dumps(q["options"]),
                        q["correct_answer"], q.get("explanation", ""), q.get("difficulty", "medium"),
                        q.get("bloom_level", "understand"), q["quiz_type"], q.get("order_idx", 0),
                        json.dumps(q.get("option_explanations")) if q.get("option_explanations") else None,
                    ),
                )
                n += cur.rowcount
    finally:
        conn.close()
    return n


def build_chapters_and_quizzes(
    video_id: str, chunks: list[dict], duration_s: float, log=None,
) -> dict:
    """Full pipeline: segment chapters → persist → generate pretest / mid_recall /
    end_recall quizzes for each → store (prompt_version=2).

    Idempotent: replaces prior auto chapters + their quizzes on re-run.
    Returns {"chapters": n, "questions": n}.
    """
    def _log(msg: str) -> None:
        (log or logger.info)(msg)

    segments = segment_chapters(video_id, chunks, duration_s)
    if not segments:
        _log("  chapters: no segments (missing chunks/duration)")
        return {"chapters": 0, "questions": 0}

    chapters = _persist_chapters(video_id, segments)
    _log(f"  → {len(chapters)} chapters")

    total_q = 0
    for ch in chapters:
        ch_minutes = (ch["end_time"] - ch["start_time"]) / 60.0

        # pretest at chapter start
        try:
            qs = generate_chapter_quizzes(video_id, ch, chunks, "pretest", count=4)
            total_q += _insert_chapter_questions(video_id, qs, int(ch["start_time"] // 30))
        except Exception as exc:  # noqa: BLE001
            _log(f"  pretest ch{ch['idx']} failed: {str(exc)[:80]}")

        # mid_recall(s) evenly spaced within the chapter
        n_mid = _compute_mid_recall_count(ch_minutes)
        for j in range(n_mid):
            mid_ts = ch["start_time"] + (ch["end_time"] - ch["start_time"]) * (j + 1) / (n_mid + 1)
            try:
                qs = generate_chapter_quizzes(
                    video_id, ch, chunks, "mid_recall", count=3, mid_recall_timestamp=mid_ts,
                )
                total_q += _insert_chapter_questions(video_id, qs, int(mid_ts // 30))
            except Exception as exc:  # noqa: BLE001
                _log(f"  mid_recall ch{ch['idx']} failed: {str(exc)[:80]}")

        # end_recall at chapter end
        try:
            qs = generate_chapter_quizzes(video_id, ch, chunks, "end_recall", count=4)
            total_q += _insert_chapter_questions(video_id, qs, int(ch["end_time"] // 30))
        except Exception as exc:  # noqa: BLE001
            _log(f"  end_recall ch{ch['idx']} failed: {str(exc)[:80]}")

    _log(f"  → {total_q} chapter quiz questions (pretest/mid_recall/end_recall)")
    return {"chapters": len(chapters), "questions": total_q}
