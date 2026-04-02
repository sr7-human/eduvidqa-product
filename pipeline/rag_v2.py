"""RAG v2: index transcript chunks + keyframes + digest into ChromaDB.

One collection per embedding model: ``eduvidqa_jina`` or ``eduvidqa_gemini``.
Each document carries metadata so retrieval can filter by video_id, type,
and timestamp.

Retrieval returns ranked chunks (re-ranked by timestamp proximity),
semantically matched keyframes, and the lecture digest.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import NotFoundError

from pipeline.embeddings_v2 import EmbeddingService

logger = logging.getLogger(__name__)


def _col_name(embedding_model: str) -> str:
    """Collection name for the given embedding backend."""
    return f"eduvidqa_{embedding_model}"


def _doc_id(video_id: str, doc_type: str, index: int | str) -> str:
    """Deterministic document ID."""
    safe_vid = re.sub(r"[^a-zA-Z0-9_-]", "_", video_id)
    return f"{safe_vid}__{doc_type}__{index}"


class LectureIndex:
    """Vector index that stores transcript chunks, keyframes, and digests."""

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        embedding_model: str = "jina",
        *,
        _embed_service: EmbeddingService | None = None,
    ) -> None:
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._backend = embedding_model
        self._embed = _embed_service or EmbeddingService(embedding_model)
        self._col = self._client.get_or_create_collection(
            name=_col_name(embedding_model),
            metadata={"hnsw:space": "cosine"},
        )

    # ── Indexing ──────────────────────────────────────────────────

    def index_video(
        self,
        video_id: str,
        chunks: list[dict],
        keyframe_manifest: list[dict],
        digest: str,
    ) -> int:
        """Index all content for one video. Returns count of embeddings stored.

        Parameters
        ----------
        video_id : str
        chunks : list[dict]
            As produced by ``chunking.chunk_transcript`` — keys:
            ``chunk_id, start_time, end_time, text, linked_keyframe_ids``.
        keyframe_manifest : list[dict]
            As produced by ``keyframes.extract_keyframes`` — keys:
            ``frame_id, timestamp, file, ssim_score``.
        digest : str
            Full lecture digest text.
        """
        total = 0

        # ── 1. Transcript chunks ─────────────────────────────────
        if chunks:
            chunk_ids: list[str] = []
            chunk_texts: list[str] = []
            chunk_metas: list[dict] = []

            for ch in chunks:
                text = ch.get("text", "").strip()
                if not text:
                    continue
                doc_id = _doc_id(video_id, "chunk", ch["chunk_id"])
                chunk_ids.append(doc_id)
                chunk_texts.append(text)
                chunk_metas.append({
                    "video_id": video_id,
                    "type": "chunk",
                    "chunk_id": ch["chunk_id"],
                    "start_time": float(ch["start_time"]),
                    "end_time": float(ch["end_time"]),
                    "linked_keyframes": ",".join(ch.get("linked_keyframe_ids", [])),
                })

            if chunk_ids:
                logger.info("Embedding %d chunks for %s …", len(chunk_ids), video_id)
                chunk_vecs = self._embed.embed_batch_text(chunk_texts)
                self._upsert_batch(chunk_ids, chunk_vecs, chunk_texts, chunk_metas)
                total += len(chunk_ids)

        # ── 2. Keyframe images ────────────────────────────────────
        if keyframe_manifest:
            kf_ids: list[str] = []
            kf_paths: list[str] = []
            kf_metas: list[dict] = []

            for kf in keyframe_manifest:
                path = kf["file"]
                if not Path(path).is_file():
                    logger.warning("Keyframe file missing: %s", path)
                    continue
                doc_id = _doc_id(video_id, "keyframe", kf["frame_id"])
                kf_ids.append(doc_id)
                kf_paths.append(path)
                kf_metas.append({
                    "video_id": video_id,
                    "type": "keyframe",
                    "frame_id": kf["frame_id"],
                    "timestamp": float(kf["timestamp"]),
                    "file": path,
                })

            if kf_ids:
                logger.info("Embedding %d keyframes for %s …", len(kf_ids), video_id)
                kf_vecs = self._embed.embed_batch_images(kf_paths)
                # Store the frame_id as the "document" text for debugging
                kf_docs = [m["frame_id"] for m in kf_metas]
                self._upsert_batch(kf_ids, kf_vecs, kf_docs, kf_metas)
                total += len(kf_ids)

        # ── 3. Lecture digest ─────────────────────────────────────
        if digest and digest.strip():
            dig_id = _doc_id(video_id, "digest", "0")
            dig_vec = self._embed.embed_text(digest[:8000])  # cap for safety
            self._col.upsert(
                ids=[dig_id],
                embeddings=[dig_vec],
                documents=[digest],
                metadatas=[{"video_id": video_id, "type": "digest"}],
            )
            total += 1

        logger.info("Indexed %d items total for video %s", total, video_id)
        return total

    # ── Retrieval ─────────────────────────────────────────────────

    def retrieve(
        self,
        question: str,
        video_id: str,
        timestamp: float,
        top_k: int = 12,
    ) -> dict[str, Any]:
        """Retrieve ranked chunks, relevant keyframes, and digest.

        Returns
        -------
        dict with keys:
            ``ranked_chunks``  — transcript chunks re-ranked by timestamp proximity.
            ``relevant_keyframes`` — keyframes from semantic search + linked to chunks.
            ``digest`` — full lecture digest text.
        """
        q_vec = self._embed.embed_text(question)

        # ── 1. Semantic search (chunks + keyframes) ──────────────
        count = self._col.count()
        if count == 0:
            return {"ranked_chunks": [], "relevant_keyframes": [], "digest": ""}

        n = min(top_k * 3, count)
        results = self._col.query(
            query_embeddings=[q_vec],
            n_results=n,
            where={"video_id": video_id},
            include=["metadatas", "documents", "distances"],
        )

        raw_chunks: list[dict] = []
        semantic_kfs: list[dict] = []
        digest_text: str = ""

        if results["metadatas"]:
            for meta, doc, dist in zip(
                results["metadatas"][0],
                results["documents"][0],
                results["distances"][0],
            ):
                sim = round(1.0 - dist, 6)
                entry_type = meta.get("type", "")
                if entry_type == "chunk":
                    raw_chunks.append({**meta, "text": doc, "similarity": sim})
                elif entry_type == "keyframe":
                    semantic_kfs.append({**meta, "similarity": sim})
                elif entry_type == "digest":
                    digest_text = doc

        # ── 2. If digest wasn't in search results, fetch directly ─
        if not digest_text:
            digest_text = self._fetch_digest(video_id)

        # ── 3. Re-rank chunks by proximity to timestamp ──────────
        raw_chunks.sort(
            key=lambda c: abs(
                (c.get("start_time", 0) + c.get("end_time", 0)) / 2 - timestamp
            )
        )
        ranked_chunks = raw_chunks[:top_k]

        # ── 4. Collect keyframes linked to ranked chunks ─────────
        linked_kf_ids: set[str] = set()
        for ch in ranked_chunks:
            lk = ch.get("linked_keyframes", "")
            if lk:
                linked_kf_ids.update(lk.split(","))

        # Merge linked keyframes with semantically retrieved ones
        seen_kf: set[str] = set()
        relevant_kfs: list[dict] = []
        for kf in semantic_kfs:
            fid = kf.get("frame_id", "")
            if fid and fid not in seen_kf:
                seen_kf.add(fid)
                relevant_kfs.append(kf)

        # Add linked keyframes that weren't already found semantically
        for fid in linked_kf_ids:
            if fid and fid not in seen_kf:
                seen_kf.add(fid)
                # Try to find this keyframe's metadata from the collection
                kf_doc_id = _doc_id(video_id, "keyframe", fid)
                try:
                    got = self._col.get(ids=[kf_doc_id], include=["metadatas"])
                    if got["metadatas"]:
                        relevant_kfs.append(got["metadatas"][0])
                except Exception:
                    relevant_kfs.append({"frame_id": fid, "video_id": video_id, "type": "keyframe"})

        return {
            "ranked_chunks": ranked_chunks,
            "relevant_keyframes": relevant_kfs,
            "digest": digest_text,
        }

    # ── Helpers ───────────────────────────────────────────────────

    def is_indexed(self, video_id: str) -> bool:
        """Check if any documents exist for this video."""
        try:
            results = self._col.get(
                where={"video_id": video_id},
                limit=1,
                include=[],
            )
            return bool(results["ids"])
        except Exception:
            return False

    def _fetch_digest(self, video_id: str) -> str:
        """Retrieve the stored digest text for a video."""
        dig_id = _doc_id(video_id, "digest", "0")
        try:
            got = self._col.get(ids=[dig_id], include=["documents"])
            if got["documents"]:
                return got["documents"][0]
        except Exception:
            pass
        return ""

    def _upsert_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
        batch_size: int = 5000,
    ) -> None:
        """Upsert in batches to respect ChromaDB limits."""
        for i in range(0, len(ids), batch_size):
            j = i + batch_size
            self._col.upsert(
                ids=ids[i:j],
                embeddings=embeddings[i:j],
                documents=documents[i:j],
                metadatas=metadatas[i:j],
            )
