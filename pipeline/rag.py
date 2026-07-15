"""RAG: index transcript chunks + keyframes + digest into Supabase pgvector.

Storage backend: Postgres (Supabase) with pgvector extension. Tables:
``videos``, ``video_chunks``, ``keyframe_embeddings`` — created by Session G.

Embeddings use Gemini Embedding 2 native 3072-dim (new videos write to
``embedding_v2``). Old videos retain 1024-dim in ``embedding`` column.
Retrieval auto-detects which column to query per video.

Retrieval returns ranked chunks (re-ranked by combined semantic + temporal
score), semantically matched keyframes, and the lecture digest.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import psycopg2
import psycopg2.extras

from backend.supabase_config import get_database_url
from pipeline.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


def _vec_literal(vec: list[float]) -> str:
    """Convert a Python list to a pgvector literal string."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


class LectureIndex:
    """Vector index backed by Supabase Postgres + pgvector."""

    def __init__(
        self,
        persist_dir: str | None = None,  # accepted for backward compat, ignored
        embedding_model: str | None = None,
        *,
        _embed_service: EmbeddingService | None = None,
        **kwargs: Any,
    ) -> None:
        self._dsn = get_database_url()
        # Default: Gemini API (fast, no local model needed). Falls back to Jina
        # automatically inside EmbeddingService if Gemini API fails.
        # Override via EMBEDDING_BACKEND env var ("gemini" or "jina").
        if embedding_model is None:
            embedding_model = os.getenv("EMBEDDING_BACKEND", "gemini")
        self._backend = embedding_model
        self._embed = _embed_service or EmbeddingService(embedding_model)

    # ── Connection helper ────────────────────────────────────────

    def _connect(self):
        return psycopg2.connect(self._dsn)

    # ── Indexing ─────────────────────────────────────────────────

    def is_indexed(self, video_id: str) -> bool:
        """True if this video has queryable transcript chunks embedded.

        Checks for actual embedded chunks rather than the ``status`` column,
        so Q&A keeps working even after Phase 2 (visual understanding) flips
        the status back to ``processing`` — the transcript is already there.
        """
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS(SELECT 1 FROM video_chunks "
                    "WHERE video_id = %s AND embedding_v2 IS NOT NULL)",
                    (video_id,),
                )
                return bool(cur.fetchone()[0])
        except Exception as exc:
            logger.warning("is_indexed failed for %s: %s", video_id, exc)
            return False

    def _existing_chunk_ids(self, video_id: str) -> set[str]:
        """chunk_ids already embedded + stored for this video (used to RESUME
        after a mid-way failure instead of re-embedding everything)."""
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT chunk_id FROM video_chunks "
                    "WHERE video_id = %s AND embedding_v2 IS NOT NULL",
                    (video_id,),
                )
                return {str(r[0]) for r in cur.fetchall()}
        except Exception as exc:  # noqa: BLE001
            logger.warning("_existing_chunk_ids failed for %s: %s", video_id, exc)
            return set()

    def _insert_chunk_rows(self, rows: list) -> None:
        """Insert one batch of embedded chunks (own short-lived connection so
        each batch is committed — partial progress survives a later failure)."""
        if not rows:
            return
        with self._connect() as conn, conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO video_chunks
                  (id, video_id, chunk_id, start_time, end_time,
                   text, embedding_v2, linked_keyframe_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)
                ON CONFLICT (video_id, chunk_id) DO UPDATE
                  SET embedding_v2 = EXCLUDED.embedding_v2
                """,
                rows,
                page_size=100,
            )

    def index_video(
        self,
        video_id: str,
        chunks: list[dict],
        keyframe_manifest: list[dict],
        digest: str,
        manage_status: bool = True,
    ) -> int:
        """Index all content for one video. Returns count of items stored.

        Inserts into ``videos`` (status=processing → ready), ``video_chunks``,
        and ``keyframe_embeddings``. Idempotent via ON CONFLICT.

        Parameters
        ----------
        manage_status : bool
            If True (default), this method sets status='processing' at start
            and status='ready' at end. Set False when the caller manages
            multi-phase status transitions (e.g. transcript_ready → ready).
        """
        total = 0
        digest_text = (digest or "").strip()[:8000]

        # ── 1. Upsert video row (status managed by caller if requested) ──
        with self._connect() as conn, conn.cursor() as cur:
            if manage_status:
                cur.execute(
                    """
                    INSERT INTO videos (id, video_id, pipeline_version, status, digest)
                    VALUES (%s, %s, 1, 'processing', %s)
                    ON CONFLICT (video_id, pipeline_version) DO UPDATE
                    SET status = 'processing',
                        digest = EXCLUDED.digest,
                        updated_at = now()
                    """,
                    (str(uuid.uuid4()), video_id, digest_text),
                )
            elif digest_text:
                # Caller manages status — only update digest if non-empty
                cur.execute(
                    """
                    INSERT INTO videos (id, video_id, pipeline_version, status, digest)
                    VALUES (%s, %s, 1, 'processing', %s)
                    ON CONFLICT (video_id, pipeline_version) DO UPDATE
                    SET digest = EXCLUDED.digest,
                        updated_at = now()
                    """,
                    (str(uuid.uuid4()), video_id, digest_text),
                )
            else:
                # Ensure row exists without changing status
                cur.execute(
                    """
                    INSERT INTO videos (id, video_id, pipeline_version, status)
                    VALUES (%s, %s, 1, 'processing')
                    ON CONFLICT (video_id, pipeline_version) DO NOTHING
                    """,
                    (str(uuid.uuid4()), video_id),
                )

        # ── 2. Embed transcript chunks INCREMENTALLY + insert per batch, so a
        #       mid-way failure (e.g. Gemini 429) KEEPS completed work and a
        #       re-run (even with a fresh key) RESUMES instead of re-embedding. ──
        if chunks:
            clean: list[dict] = []
            for ch in chunks:
                text = (ch.get("text") or "").strip()
                if text:
                    clean.append({**ch, "text": text})

            if clean:
                already = self._existing_chunk_ids(video_id)
                todo = [c for c in clean if str(c["chunk_id"]) not in already]
                if already:
                    logger.info(
                        "Resuming %s: %d/%d chunks already embedded, %d to go",
                        video_id, len(already), len(clean), len(todo),
                    )
                else:
                    logger.info("Embedding %d chunks for %s …", len(todo), video_id)

                _GROUP = 48
                for gi in range(0, len(todo), _GROUP):
                    group = todo[gi:gi + _GROUP]
                    vecs = self._embed.embed_batch_text([c["text"] for c in group])
                    rows = [
                        (
                            str(uuid.uuid4()), video_id, str(ch["chunk_id"]),
                            float(ch["start_time"]), float(ch["end_time"]),
                            ch["text"], _vec_literal(vec),
                            list(ch.get("linked_keyframe_ids") or []),
                        )
                        for ch, vec in zip(group, vecs)
                    ]
                    # Commit this batch immediately → progress persists on failure.
                    self._insert_chunk_rows(rows)
                    total += len(rows)

        # ── 3. Embed keyframes (no DB connection held) ──
        kf_rows: list[tuple] = []
        if keyframe_manifest:
            from pathlib import Path as _P

            valid: list[dict] = []
            for kf in keyframe_manifest:
                path = kf.get("file", "")
                if path and _P(path).is_file():
                    valid.append(kf)
                else:
                    logger.warning("Keyframe file missing: %s", path)

            if valid:
                logger.info("Embedding %d keyframes for %s …", len(valid), video_id)
                vecs = self._embed.embed_batch_images([k["file"] for k in valid])
                # Upload each keyframe to Supabase Storage in parallel-friendly batches
                # so the public URL (rather than a local file path) is what we persist.
                # This makes keyframes accessible from any backend (local + HF Spaces).
                from pipeline.storage import upload_keyframe_batch
                public_urls = upload_keyframe_batch(video_id, valid)
                import math
                for kf, vec, public_url in zip(valid, vecs, public_urls):
                    if any((v is None) or math.isnan(float(v)) or math.isinf(float(v)) for v in vec):
                        logger.warning("Skipping keyframe %s: NaN/Inf in embedding", kf["frame_id"])
                        continue
                    # Prefer the Supabase URL; fall back to local path if upload failed.
                    storage_path = public_url or kf["file"]
                    kf_rows.append((
                        str(uuid.uuid4()),
                        video_id,
                        str(kf["frame_id"]),
                        float(kf["timestamp"]),
                        storage_path,
                        _vec_literal(vec),
                    ))

        # ── 4. Bulk insert keyframes + mark ready (chunks already inserted above) ──
        with self._connect() as conn:
            if kf_rows:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_batch(
                        cur,
                        """
                        INSERT INTO keyframe_embeddings
                          (id, video_id, keyframe_id, timestamp_seconds,
                           storage_path, embedding_v2)
                        VALUES (%s, %s, %s, %s, %s, %s::vector)
                        ON CONFLICT (video_id, keyframe_id) DO UPDATE
                          SET embedding_v2 = EXCLUDED.embedding_v2
                        """,
                        kf_rows,
                        page_size=100,
                    )
                total += len(kf_rows)

            with conn.cursor() as cur:
                if manage_status:
                    cur.execute(
                        "UPDATE videos SET status = 'ready', updated_at = now() "
                        "WHERE video_id = %s AND pipeline_version = 1",
                        (video_id,),
                    )

        logger.info("Indexed %d items total for video %s", total, video_id)
        return total

    # ── Retrieval ────────────────────────────────────────────────

    def retrieve(
        self,
        question: str,
        video_id: str,
        timestamp: float,
        top_k: int = 12,
        start_time: float | None = None,
        end_time: float | None = None,
        whole_video: bool = False,
    ) -> dict[str, Any]:
        """Return ranked chunks + relevant keyframes + digest for a question.

        Auto-detects whether the video uses v2 (3072-dim) or v1 (1024-dim)
        embeddings and generates the query vector at the matching dimension.

        When ``start_time`` and ``end_time`` are both given (RANGE mode), only
        transcript chunks and keyframes inside ``[start_time, end_time)`` are
        considered, and the whole-video digest is omitted so no evidence from
        outside the selected interval leaks into the answer.
        """
        range_mode = start_time is not None and end_time is not None
        center = ((float(start_time) + float(end_time)) / 2.0) if range_mode else float(timestamp)
        # Detect which embedding column this video uses
        use_v2 = False
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM video_chunks "
                "WHERE video_id = %s AND embedding_v2 IS NOT NULL LIMIT 1)",
                (video_id,),
            )
            use_v2 = bool(cur.fetchone()[0])

        emb_col = "embedding_v2" if use_v2 else "embedding"
        if use_v2:
            q_vec = self._embed.embed_text(question)       # 3072-dim native
        else:
            q_vec = self._embed.embed_text_legacy(question) # 1024-dim compressed
        q_lit = _vec_literal(q_vec)

        with self._connect() as conn, conn.cursor() as cur:
            # ── 1. Nearest chunks (over-fetch for re-ranking) ──
            cur.execute(
                f"""
                SELECT chunk_id, text, start_time, end_time,
                       linked_keyframe_ids,
                       1 - ({emb_col} <=> %s::vector) AS similarity
                FROM video_chunks
                WHERE video_id = %s
                ORDER BY {emb_col} <=> %s::vector
                LIMIT %s
                """,
                (q_lit, video_id, q_lit, top_k * 2),
            )
            chunk_rows = cur.fetchall()

            # ── 2. Nearest keyframes ───────────────────────────
            cur.execute(
                f"""
                SELECT keyframe_id, timestamp_seconds, storage_path,
                       1 - ({emb_col} <=> %s::vector) AS similarity
                FROM keyframe_embeddings
                WHERE video_id = %s
                ORDER BY {emb_col} <=> %s::vector
                LIMIT 5
                """,
                (q_lit, video_id, q_lit),
            )
            kf_rows = cur.fetchall()

            # ── 3. Digest ──────────────────────────────────────
            cur.execute(
                "SELECT digest FROM videos WHERE video_id = %s "
                "AND pipeline_version = 1",
                (video_id,),
            )
            row = cur.fetchone()
            digest_text = (row[0] if row and row[0] else "") or ""

        # ── 4. Re-rank chunks: combined semantic + temporal ────
        # Whole-lecture mode → alpha 0 = pure semantic, so the most relevant
        # parts anywhere in the video win (no bias toward the current moment).
        alpha = 0.0 if whole_video else 0.3
        ranked: list[dict] = []
        for chunk_id, text, c_start, c_end, linked, sim in chunk_rows:
            mid = (float(c_start) + float(c_end)) / 2.0
            temporal = 1.0 / (1.0 + abs(mid - center) / 60.0)
            combined = (1 - alpha) * float(sim) + alpha * temporal
            ranked.append({
                "chunk_id": chunk_id,
                "text": text,
                "start_time": float(c_start),
                "end_time": float(c_end),
                "relevance_score": round(combined, 6),
                "video_id": video_id,
                "type": "chunk",
                "linked_keyframes": ",".join(linked or []),
            })
        ranked.sort(key=lambda c: c["relevance_score"], reverse=True)
        ranked_chunks = ranked[:top_k]

        # ── 5. Build keyframe list (semantic + linked) ────────
        seen: set[str] = set()
        relevant_kfs: list[dict] = []
        for keyframe_id, ts, storage_path, sim in kf_rows:
            if keyframe_id in seen:
                continue
            seen.add(keyframe_id)
            relevant_kfs.append({
                "frame_id": keyframe_id,
                "timestamp": float(ts),
                "file": storage_path,
                "video_id": video_id,
                "type": "keyframe",
                "similarity": round(float(sim), 6),
            })

        # Pull in keyframes linked to ranked chunks (if not already present)
        linked_ids: set[str] = set()
        for ch in ranked_chunks:
            lk = ch.get("linked_keyframes", "")
            if lk:
                linked_ids.update(x for x in lk.split(",") if x)
        missing = [fid for fid in linked_ids if fid not in seen]
        if missing:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT keyframe_id, timestamp_seconds, storage_path
                    FROM keyframe_embeddings
                    WHERE video_id = %s AND keyframe_id = ANY(%s)
                    """,
                    (video_id, missing),
                )
                for keyframe_id, ts, storage_path in cur.fetchall():
                    if keyframe_id in seen:
                        continue
                    seen.add(keyframe_id)
                    relevant_kfs.append({
                        "frame_id": keyframe_id,
                        "timestamp": float(ts),
                        "file": storage_path,
                        "video_id": video_id,
                        "type": "keyframe",
                        "similarity": 0.0,
                    })

        return {
            "ranked_chunks": ranked_chunks,
            "relevant_keyframes": relevant_kfs[:3],
            "digest": digest_text,
        }
