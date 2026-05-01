"""Embedding service: Gemini Embedding 2 (API, 1024-dim, multimodal).

Used for both transcript chunks (text) and lecture keyframes (images).
A single API call can batch 50–100 inputs.

Usage:
    svc = EmbeddingService()             # uses GEMINI_API_KEY from env
    text_vec = svc.embed_text("what is sorting?")
    img_vec  = svc.embed_image("kf_000035.jpg")
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-2-preview"
DIM = 1024


class EmbeddingService:
    """Gemini multimodal embeddings (text + images), batched and retry-aware."""

    def __init__(self, model: str = "gemini") -> None:
        # `model` arg kept for backward-compat with old callers; only "gemini"
        # is supported now. Anything else still maps to gemini.
        self._backend = "gemini"
        self._client = None  # lazy

    # ── Lazy init ─────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY env var not set")
        self._client = genai.Client(api_key=api_key)
        logger.info("Gemini Embedding client initialised (dim=%d)", DIM)

    # Compatibility shim — some code still calls _ensure_loaded().
    def _ensure_loaded(self) -> None:
        self._ensure_client()

    def get_dimension(self) -> int:
        return DIM

    # ── Text ──────────────────────────────────────────────────────

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch_text([text])[0]

    def embed_batch_text(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_client()
        from google.genai import types

        out: list[list[float]] = []
        BATCH = 100  # Gemini embed_content per-request limit
        for i in range(0, len(texts), BATCH):
            chunk = texts[i : i + BATCH]
            out.extend(
                list(e.values)
                for e in self._call_with_retry(
                    contents=chunk,
                    config=types.EmbedContentConfig(output_dimensionality=DIM),
                ).embeddings
            )
        return out

    # ── Images ────────────────────────────────────────────────────

    def embed_image(self, image_path: str) -> list[float]:
        return self.embed_batch_images([image_path])[0]

    def embed_batch_images(self, paths: list[str]) -> list[list[float]]:
        if not paths:
            return []
        self._ensure_client()
        from google.genai import types

        out: list[list[float]] = []
        BATCH = 50  # images heavier than text — smaller batch
        for i in range(0, len(paths), BATCH):
            chunk_paths = paths[i : i + BATCH]
            parts = []
            for p in chunk_paths:
                mime = "image/png" if p.lower().endswith(".png") else "image/jpeg"
                parts.append(
                    types.Part.from_bytes(data=Path(p).read_bytes(), mime_type=mime)
                )
            out.extend(
                list(e.values)
                for e in self._call_with_retry(
                    contents=parts,
                    config=types.EmbedContentConfig(output_dimensionality=DIM),
                ).embeddings
            )
        return out

    # ── Internal: call with simple retry on 503 / 429 ────────────

    def _call_with_retry(self, *, contents, config, max_attempts: int = 3):
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self._client.models.embed_content(
                    model=EMBED_MODEL,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                msg = str(exc)
                if any(
                    s in msg
                    for s in ("503", "UNAVAILABLE", "overloaded", "429", "RESOURCE_EXHAUSTED")
                ):
                    sleep_for = 2 ** attempt
                    logger.warning(
                        "Gemini embed call failed (%s) — retrying in %ds",
                        msg[:80],
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                raise
        raise last_exc if last_exc else RuntimeError("Gemini embed call failed")
