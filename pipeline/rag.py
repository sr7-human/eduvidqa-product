"""RAG pipeline: index lecture segments and retrieve relevant chunks."""

from __future__ import annotations

import logging
import re
from typing import Optional

import chromadb

from pipeline.embeddings import EmbeddingModel
from pipeline.models import RetrievalResult, RetrievedContext, VideoSegment

logger = logging.getLogger(__name__)

# If a segment transcript exceeds this word count, split into sub-chunks.
_MAX_WORDS_PER_CHUNK = 500
# Overlap: 1 sentence carried into the next sub-chunk.
_OVERLAP_SENTENCES = 1


def _split_into_sentences(text: str) -> list[str]:
    """Rudimentary sentence splitter (period / question mark / exclamation)."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in parts if s]


def _subchunk(transcript: str) -> list[str]:
    """Split a long transcript into sub-chunks with 1-sentence overlap."""
    sentences = _split_into_sentences(transcript)
    if not sentences:
        return [transcript]

    chunks: list[str] = []
    current: list[str] = []
    word_count = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if word_count + sent_words > _MAX_WORDS_PER_CHUNK and current:
            chunks.append(" ".join(current))
            # Carry last _OVERLAP_SENTENCES sentence(s) into next chunk
            overlap = current[-_OVERLAP_SENTENCES:]
            current = list(overlap)
            word_count = sum(len(s.split()) for s in current)
        current.append(sent)
        word_count += sent_words

    if current:
        chunks.append(" ".join(current))

    return chunks


def _collection_name(video_id: str) -> str:
    """Derive a ChromaDB collection name from a video ID.

    ChromaDB collection names must:
    - Be 3-63 chars, start/end with alphanumeric, contain only
      alphanumeric, underscores, or hyphens.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", video_id)
    name = f"video_{sanitized}"
    # Ensure length bounds
    if len(name) < 3:
        name = name + "___"[:3 - len(name)]
    return name[:63]


class LectureIndex:
    """Vector index for a single lecture video's segments."""

    def __init__(
        self,
        persist_dir: str = "./data/chroma",
        embedding_model: Optional[EmbeddingModel] = None,
    ) -> None:
        """Initialize ChromaDB client and embedding model."""
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embed = embedding_model or EmbeddingModel()

    # ── Indexing ──────────────────────────────────────────────────

    def index_segments(self, segments: list[VideoSegment]) -> int:
        """Embed and store all segments for a video.

        If a segment transcript > 500 words it is split into sub-chunks with
        1-sentence overlap.  Each sub-chunk stores the parent segment metadata
        so we can reconstruct the full ``VideoSegment`` on retrieval.

        Returns:
            Number of segments indexed (original segment count, not sub-chunks).
        """
        if not segments:
            return 0

        video_id = segments[0].video_id
        col_name = _collection_name(video_id)

        # Recreate collection (idempotent: wipe old data for this video)
        try:
            self._client.delete_collection(col_name)
        except ValueError:
            pass  # collection didn't exist yet
        collection = self._client.get_or_create_collection(
            name=col_name, metadata={"hnsw:space": "cosine"}
        )

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for seg in segments:
            chunks = _subchunk(seg.transcript_text)
            for chunk_idx, chunk_text in enumerate(chunks):
                doc_id = f"{video_id}_seg{seg.segment_index}_c{chunk_idx}"
                ids.append(doc_id)
                documents.append(chunk_text)
                metadatas.append(
                    {
                        "video_id": seg.video_id,
                        "segment_index": seg.segment_index,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "transcript_text": seg.transcript_text,
                        "frame_paths": ",".join(seg.frame_paths),
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                    }
                )

        # Embed all document texts at once
        embeddings = self._embed.embed_batch(documents, is_query=False)

        # ChromaDB upsert (batched — Chroma has a soft limit of ~5461 per call)
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            j = i + batch_size
            collection.upsert(
                ids=ids[i:j],
                embeddings=embeddings[i:j],
                documents=documents[i:j],
                metadatas=metadatas[i:j],
            )

        logger.info(
            "Indexed %d segments (%d sub-chunks) for video %s",
            len(segments),
            len(ids),
            video_id,
        )
        return len(segments)

    # ── Query helpers ─────────────────────────────────────────────

    def is_indexed(self, video_id: str) -> bool:
        """Check if a video has already been indexed (avoid re-embedding)."""
        col_name = _collection_name(video_id)
        try:
            col = self._client.get_collection(col_name)
            return col.count() > 0
        except ValueError:
            return False

    def retrieve(
        self,
        query: str,
        video_id: str,
        top_k: int = 5,
    ) -> RetrievalResult:
        """Find the top-K most relevant segments for a student question.

        Returns a ``RetrievalResult`` with ranked ``RetrievedContext`` objects.
        If multiple sub-chunks belong to the same parent segment, only the
        highest-scoring sub-chunk is kept (de-duplication).
        """
        col_name = _collection_name(video_id)
        try:
            collection = self._client.get_collection(col_name)
        except ValueError as exc:
            raise ValueError(
                f"Video '{video_id}' has not been indexed yet."
            ) from exc

        total_segments = collection.count()

        query_vec = self._embed.embed_text(query, is_query=True)
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=min(top_k * 3, total_segments),  # fetch extra for dedup
            include=["metadatas", "distances"],
        )

        # ChromaDB returns cosine *distance* (0 = identical). Convert to
        # similarity: sim = 1 - distance.
        seen_segments: set[int] = set()
        contexts: list[RetrievedContext] = []

        if results["metadatas"] and results["distances"]:
            for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
                seg_idx = int(meta["segment_index"])
                if seg_idx in seen_segments:
                    continue
                seen_segments.add(seg_idx)

                frame_paths_raw = meta.get("frame_paths", "")
                frame_paths = (
                    frame_paths_raw.split(",") if frame_paths_raw else []
                )

                segment = VideoSegment(
                    video_id=str(meta["video_id"]),
                    segment_index=seg_idx,
                    start_time=float(meta["start_time"]),
                    end_time=float(meta["end_time"]),
                    transcript_text=str(meta["transcript_text"]),
                    frame_paths=frame_paths,
                )

                contexts.append(
                    RetrievedContext(
                        segment=segment,
                        relevance_score=round(1.0 - dist, 6),
                        rank=0,  # assigned below
                    )
                )

                if len(contexts) >= top_k:
                    break

        # Sort by descending relevance and assign 1-based ranks
        contexts.sort(key=lambda c: c.relevance_score, reverse=True)
        for i, ctx in enumerate(contexts):
            ctx.rank = i + 1

        return RetrievalResult(
            query=query,
            video_id=video_id,
            contexts=contexts,
            total_segments=total_segments,
        )

    # ── Cleanup ───────────────────────────────────────────────────

    def delete_video(self, video_id: str) -> bool:
        """Remove all indexed segments for a video."""
        col_name = _collection_name(video_id)
        try:
            self._client.delete_collection(col_name)
            logger.info("Deleted index for video %s", video_id)
            return True
        except ValueError:
            return False
