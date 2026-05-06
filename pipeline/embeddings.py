"""Embedding service: Gemini Embedding 2 (API, 3072-dim native, multimodal).

Used for both transcript chunks (text) and lecture keyframes (images).
A single API call can batch 50–100 inputs.

New videos use native 3072-dim embeddings (embedding_v2 column).
Old videos may still have 1024-dim embeddings (embedding column).
Retrieval code in rag.py handles both dimensions transparently.

Usage:
    svc = EmbeddingService()             # uses GEMINI_API_KEY from env
    text_vec = svc.embed_text("what is sorting?")   # 3072-dim
    img_vec  = svc.embed_image("kf_000035.jpg")     # 3072-dim
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-2-preview"
DIM = 3072
DIM_LEGACY = 1024  # old videos still have 1024-dim embeddings


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
        # Gemini batchEmbedContents accepts up to 100 items per request.
        # Avg keyframe ~45 KB → 100 imgs ≈ 4.5 MB raw / 6 MB base64, well
        # under the 20 MB request-body cap, so we use the full 100.
        BATCH = 100
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
                ).embeddings
            )
        return out

    # ── Internal: call with simple retry on 503 / 429 ────────────

    def embed_text_legacy(self, text: str) -> list[float]:
        """Embed text at 1024-dim for querying old videos with v1 embeddings."""
        self._ensure_client()
        from google.genai import types
        result = self._call_with_retry(
            contents=[text],
            config=types.EmbedContentConfig(output_dimensionality=DIM_LEGACY),
        )
        return list(result.embeddings[0].values)

    def _call_with_retry(self, *, contents, config=None, max_attempts: int = 6):
        import re

        last_exc: Exception | None = None
        kwargs: dict = {"model": EMBED_MODEL, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        for attempt in range(max_attempts):
            try:
                return self._client.models.embed_content(**kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                msg = str(exc)
                if any(
                    s in msg
                    for s in ("503", "UNAVAILABLE", "overloaded", "429", "RESOURCE_EXHAUSTED")
                ):
                    # Gemini sometimes tells us how long to wait — honour it.
                    server_hint: float | None = None
                    m = re.search(r"retry in ([\d.]+)s", msg, re.IGNORECASE)
                    if m:
                        try:
                            server_hint = float(m.group(1))
                        except ValueError:
                            server_hint = None
                    sleep_for = server_hint if server_hint else min(2 ** attempt, 30)
                    # Pad slightly so we land just after the quota window resets.
                    sleep_for = sleep_for + 1.0
                    logger.warning(
                        "Gemini embed call failed (%s) — retry %d/%d in %.1fs",
                        msg[:120], attempt + 1, max_attempts, sleep_for,
                    )
                    time.sleep(sleep_for)
                    continue
                raise
        raise last_exc if last_exc else RuntimeError("Gemini embed call failed")
