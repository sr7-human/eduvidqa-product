"""RAG: index transcript chunks + keyframes + digest into Supabase pgvector.

Storage backend: Postgres (Supabase) with pgvector extension. Tables:
``videos``, ``video_chunks``, ``keyframe_embeddings`` — created by Session G.

Embeddings stay in the same 1024-dim Jina CLIP v2 space (text + images).

Retrieval returns ranked chunks (re-ranked by combined semantic + temporal
score), semantically matched keyframes, and the lecture digest.
"""

from __future__ import annotations

import logging
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
        embedding_model: str = "jina",
        *,
        _embed_service: EmbeddingService | None = None,
        **kwargs: Any,
    ) -> None:
        self._dsn = get_database_url()
        self._backend = embedding_model
        self._embed = _embed_service or EmbeddingService(embedding_model)

    # ── Connection helper ────────────────────────────────────────

    def _connect(self):
        return psycopg2.connect(self._dsn)

    # ── Indexing ─────────────────────────────────────────────────

    def is_indexed(self, video_id: str) -> bool:
        """True if a `ready` row exists for this video_id."""
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS(SELECT 1 FROM videos "
                    "WHERE video_id = %s AND status = 'ready')",
                    (video_id,),
                )
                return bool(cur.fetchone()[0])
        except Exception as exc:
            logger.warning("is_indexed failed for %s: %s", video_id, exc)
            return False

    def index_video(
        self,
        video_id: str,
        chunks: list[dict],
        keyframe_manifest: list[dict],
        digest: str,
    ) -> int:
        """Index all content for one video. Returns count of items stored.

        Inserts into ``videos`` (status=processing → ready), ``video_chunks``,
        and ``keyframe_embeddings``. Idempotent via ON CONFLICT.
        """
        total = 0
        digest_text = (digest or "").strip()[:8000]

        # ── 1. Upsert video row to processing (fresh connection) ──
        with self._connect() as conn, conn.cursor() as cur:
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

        # ── 2. Embed transcript chunks (no DB connection held) ──
        chunk_rows: list[tuple] = []
        if chunks:
            clean: list[dict] = []
            for ch in chunks:
                text = (ch.get("text") or "").strip()
                if text:
                    clean.append({**ch, "text": text})

            if clean:
                logger.info("Embedding %d chunks for %s …", len(clean), video_id)
                vecs = self._embed.embed_batch_text([c["text"] for c in clean])
                for ch, vec in zip(clean, vecs):
                    chunk_rows.append((
                        str(uuid.uuid4()),
                        video_id,
                        str(ch["chunk_id"]),
                        float(ch["start_time"]),
                        float(ch["end_time"]),
                        ch["text"],
                        _vec_literal(vec),
                        list(ch.get("linked_keyframe_ids") or []),
                    ))

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
                import math
                for kf, vec in zip(valid, vecs):
                    if any((v is None) or math.isnan(float(v)) or math.isinf(float(v)) for v in vec):
                        logger.warning("Skipping keyframe %s: NaN/Inf in embedding", kf["frame_id"])
                        continue
                    kf_rows.append((
                        str(uuid.uuid4()),
                        video_id,
                        str(kf["frame_id"]),
                        float(kf["timestamp"]),
                        kf["file"],
                        _vec_literal(vec),
                    ))

        # ── 4. Bulk insert + mark ready (fresh short-lived connection) ──
        with self._connect() as conn:
            if chunk_rows:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_batch(
                        cur,
                        """
                        INSERT INTO video_chunks
                          (id, video_id, chunk_id, start_time, end_time,
                           text, embedding, linked_keyframe_ids)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)
                        ON CONFLICT (video_id, chunk_id) DO NOTHING
                        """,
                        chunk_rows,
                        page_size=100,
                    )
                total += len(chunk_rows)

            if kf_rows:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_batch(
                        cur,
                        """
                        INSERT INTO keyframe_embeddings
                          (id, video_id, keyframe_id, timestamp_seconds,
                           storage_path, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s::vector)
                        ON CONFLICT (video_id, keyframe_id) DO NOTHING
                        """,
                        kf_rows,
                        page_size=100,
                    )
                total += len(kf_rows)

            with conn.cursor() as cur:
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
    ) -> dict[str, Any]:
        """Return ranked chunks + relevant keyframes + digest for a question."""
        q_vec = self._embed.embed_text(question)
        q_lit = _vec_literal(q_vec)

        with self._connect() as conn, conn.cursor() as cur:
            # ── 1. Nearest chunks (over-fetch for re-ranking) ──
            cur.execute(
                """
                SELECT chunk_id, text, start_time, end_time,
                       linked_keyframe_ids,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM video_chunks
                WHERE video_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (q_lit, video_id, q_lit, top_k * 2),
            )
            chunk_rows = cur.fetchall()

            # ── 2. Nearest keyframes ───────────────────────────
            cur.execute(
                """
                SELECT keyframe_id, timestamp_seconds, storage_path,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM keyframe_embeddings
                WHERE video_id = %s
                ORDER BY embedding <=> %s::vector
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
        alpha = 0.3
        ranked: list[dict] = []
        for chunk_id, text, start_time, end_time, linked, sim in chunk_rows:
            mid = (float(start_time) + float(end_time)) / 2.0
            temporal = 1.0 / (1.0 + abs(mid - float(timestamp)) / 60.0)
            combined = (1 - alpha) * float(sim) + alpha * temporal
            ranked.append({
                "chunk_id": chunk_id,
                "text": text,
                "start_time": float(start_time),
                "end_time": float(end_time),
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
