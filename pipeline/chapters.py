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
import math
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

# A chapter longer than this (minutes) is subdivided into ~_SUBDIVIDE_TARGET_MIN
# sub-chapters. Only applied to creator (YouTube) chapters — the progressive
# formula already sizes its own segments.
_MAX_CHAPTER_MIN = 20.0
_SUBDIVIDE_TARGET_MIN = 16.0


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


def segment_chapters(
    video_id: str,
    chunks: list[dict],
    duration_s: float,
    youtube_chapters: list[dict] | None = None,
) -> list[dict]:
    """Split a video into chapters and return {idx, start_time, end_time, title}.

    Boundary source (in order):
    1. **Creator YouTube chapters** (``youtube_chapters`` from yt-dlp) — real,
       semantically-authored. Used as-is, then any chapter longer than
       ``_MAX_CHAPTER_MIN`` is subdivided into ~``_SUBDIVIDE_TARGET_MIN`` sub-
       chapters (sub-parts inherit the parent title + " (Part N)").
    2. **Progressive time formula** (``_compute_chapter_count``) when there are
       no creator chapters — already sized, so not further subdivided.

    Chapters without a title (formula path, or untitled creator chapters) are
    titled by one LLM call.
    """
    if not chunks or duration_s <= 0:
        return []

    base = _base_segments_from_youtube(youtube_chapters, duration_s)
    if base is not None:
        # Creator chapters → subdivide the over-long ones.
        segments: list[dict] = []
        for seg in base:
            segments.extend(_subdivide_segment(seg))
    else:
        # No creator chapters → progressive even split (already sized).
        n = _compute_chapter_count(duration_s / 60.0)
        span = duration_s / n
        segments = [
            {"start_time": i * span,
             "end_time": duration_s if i == n - 1 else (i + 1) * span,
             "title": None}
            for i in range(n)
        ]

    for i, seg in enumerate(segments):
        seg["idx"] = i

    # Title any segment that doesn't already have one (single LLM call).
    need = [s for s in segments if not s.get("title")]
    if need:
        titles = _title_segments(need, chunks)
        for s, t in zip(need, titles):
            s["title"] = t
    for i, s in enumerate(segments):
        if not s.get("title"):
            s["title"] = f"Part {i + 1}"
    return segments


def _base_segments_from_youtube(
    youtube_chapters: list[dict] | None, duration_s: float
) -> list[dict] | None:
    """Turn yt-dlp chapters into base segments, or None if none usable."""
    if not youtube_chapters:
        return None
    segs: list[dict] = []
    for ch in youtube_chapters:
        try:
            st = float(ch.get("start_time", 0) or 0)
            en = float(ch.get("end_time") or 0)
        except (TypeError, ValueError):
            continue
        en = min(en, duration_s)
        if en <= st:
            continue
        segs.append({"start_time": st, "end_time": en,
                     "title": (ch.get("title") or "").strip() or None})
    return segs or None


def _subdivide_segment(seg: dict) -> list[dict]:
    """Split a segment into ~equal sub-segments if it exceeds _MAX_CHAPTER_MIN."""
    length_min = (seg["end_time"] - seg["start_time"]) / 60.0
    if length_min <= _MAX_CHAPTER_MIN:
        return [dict(seg)]
    parts = max(2, math.ceil(length_min / _SUBDIVIDE_TARGET_MIN))
    span = (seg["end_time"] - seg["start_time"]) / parts
    base_title = seg.get("title")
    out: list[dict] = []
    for j in range(parts):
        s = seg["start_time"] + j * span
        e = seg["end_time"] if j == parts - 1 else seg["start_time"] + (j + 1) * span
        out.append({
            "start_time": s, "end_time": e,
            "title": f"{base_title} (Part {j + 1})" if base_title else None,
        })
    return out


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
    quiz_types: list[str] | None = None,
    youtube_chapters: list[dict] | None = None,
) -> dict:
    """Full pipeline: segment chapters → persist → generate the requested chapter
    quiz types (default: all — pretest / mid_recall / end_recall) → store
    (prompt_version=2).

    Pass ``quiz_types=["pretest"]`` to generate ONLY pretests at ingest and defer
    the rest to on-demand generation (keeps ingest cheap on LLM quota).
    Pass ``youtube_chapters`` (from ``ingest.get_youtube_chapters``) to use the
    creator's real chapter boundaries instead of the time formula.

    Idempotent: replaces prior auto chapters + their quizzes on re-run.
    Returns {"chapters": n, "questions": n}.
    """
    wanted = set(quiz_types or ["pretest", "mid_recall", "end_recall"])

    def _log(msg: str) -> None:
        (log or logger.info)(msg)

    segments = segment_chapters(video_id, chunks, duration_s, youtube_chapters=youtube_chapters)
    if not segments:
        _log("  chapters: no segments (missing chunks/duration)")
        return {"chapters": 0, "questions": 0}

    chapters = _persist_chapters(video_id, segments)
    _log(f"  → {len(chapters)} chapters")

    total_q = 0
    for ch in chapters:
        ch_minutes = (ch["end_time"] - ch["start_time"]) / 60.0

        # pretest at chapter start
        if "pretest" in wanted:
            try:
                qs = generate_chapter_quizzes(video_id, ch, chunks, "pretest", count=4)
                total_q += _insert_chapter_questions(video_id, qs, int(ch["start_time"] // 30))
            except Exception as exc:  # noqa: BLE001
                _log(f"  pretest ch{ch['idx']} failed: {str(exc)[:80]}")

        # mid_recall(s) evenly spaced within the chapter
        if "mid_recall" in wanted:
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
        if "end_recall" in wanted:
            try:
                qs = generate_chapter_quizzes(video_id, ch, chunks, "end_recall", count=4)
                total_q += _insert_chapter_questions(video_id, qs, int(ch["end_time"] // 30))
            except Exception as exc:  # noqa: BLE001
                _log(f"  end_recall ch{ch['idx']} failed: {str(exc)[:80]}")

    _log(f"  → {total_q} chapter quiz questions ({', '.join(sorted(wanted))})")
    return {"chapters": len(chapters), "questions": total_q}
