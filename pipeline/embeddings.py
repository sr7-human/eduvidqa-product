"""Embedding model wrapper for the RAG pipeline."""

from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Instruction prefixes for BGE-M3 (improves retrieval quality)
_DOC_PREFIX = "Represent this educational lecture content: "
_QUERY_PREFIX = "Represent this student question for retrieval: "


class EmbeddingModel:
    """Wrapper around sentence-transformers embedding model."""

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        """Load embedding model. Falls back to all-MiniLM-L6-v2 if OOM."""
        self.model_name = model_name
        self._is_bge = "bge" in model_name.lower()
        try:
            logger.info("Loading embedding model: %s", model_name)
            self._model = SentenceTransformer(model_name)
            logger.info("Model loaded successfully (%s)", model_name)
        except (RuntimeError, MemoryError):
            fallback = "all-MiniLM-L6-v2"
            logger.warning(
                "Failed to load %s (likely OOM). Falling back to %s",
                model_name,
                fallback,
            )
            self.model_name = fallback
            self._is_bge = False
            self._model = SentenceTransformer(fallback)

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._model.get_sentence_embedding_dimension()

    def embed_text(self, text: str, *, is_query: bool = False) -> list[float]:
        """Embed a single text string. Returns vector."""
        prefix = self._get_prefix(is_query)
        vector = self._model.encode(prefix + text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(
        self, texts: list[str], *, is_query: bool = False, batch_size: int = 32
    ) -> list[list[float]]:
        """Embed multiple texts efficiently. Returns list of vectors."""
        prefix = self._get_prefix(is_query)
        prefixed = [prefix + t for t in texts]
        vectors = self._model.encode(
            prefixed, normalize_embeddings=True, batch_size=batch_size, show_progress_bar=len(texts) > 50
        )
        return vectors.tolist()

    def _get_prefix(self, is_query: bool) -> str:
        """Return the appropriate instruction prefix for BGE models."""
        if not self._is_bge:
            return ""
        return _QUERY_PREFIX if is_query else _DOC_PREFIX
