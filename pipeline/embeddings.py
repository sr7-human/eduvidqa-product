"""Dual embedding service: Jina CLIP v2 (local) or Gemini Embedding 2 (API).

Jina CLIP v2 embeds BOTH text and images into the SAME 1024-dim space.
Gemini Embedding 2 embeds text and images into a 768-dim space via API.

Usage:
    svc = EmbeddingService("jina")          # local, free
    svc = EmbeddingService("gemini")        # API, higher quality

    text_vec = svc.embed_text("what is sorting?")
    img_vec  = svc.embed_image("kf_000035.jpg")
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Unified embedding interface for text + images."""

    def __init__(self, model: str = "jina") -> None:
        """
        Parameters
        ----------
        model : str
            ``"jina"`` — Jina CLIP v2 (local, 1024-dim, free).
            ``"gemini"`` — Gemini Embedding 2 (API, 768-dim).
        """
        if model not in ("jina", "gemini"):
            raise ValueError(f"Unknown model: {model!r}. Use 'jina' or 'gemini'.")
        self._backend = model
        self._model = None  # lazy-loaded

    # ── Lazy loading ──────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        if self._backend == "jina":
            self._load_jina()
        else:
            self._load_gemini()

    def _load_jina(self) -> None:
        from sentence_transformers import SentenceTransformer

        # Jina CLIP v2's EVA model calls .item() on torch.linspace output which
        # fails with meta tensors in PyTorch ≥2.11. Patch it at runtime.
        self._patch_jina_eva_model()

        logger.info("Loading Jina CLIP v2 …")
        self._model = SentenceTransformer(
            "jinaai/jina-clip-v2", trust_remote_code=True
        )
        logger.info("Jina CLIP v2 loaded (dim=%d)", self.get_dimension())

    @staticmethod
    def _patch_jina_eva_model() -> None:
        """Patch cached Jina EVA model to avoid torch.linspace meta tensor issue."""
        from pathlib import Path as _Path

        cache_dir = _Path.home() / ".cache" / "huggingface" / "modules" / "transformers_modules"
        pattern = "jinaai/jina_hyphen_clip_hyphen_implementation"
        for eva_file in cache_dir.glob(f"{pattern}/*/eva_model.py"):
            code = eva_file.read_text(encoding="utf-8")
            # Replace the problematic torch.linspace().item() pattern with pure Python
            needle = "x.item() for x in torch.linspace(0, drop_path_rate, depth)"
            replacement = "(drop_path_rate * i / (depth - 1) if depth > 1 else 0.0) for i in range(depth)"
            if needle in code:
                eva_file.write_text(code.replace(needle, replacement), encoding="utf-8")
                logger.info("Patched %s: torch.linspace → pure Python", eva_file)
            else:
                # May have been previously patched with float(x) — fix that too
                needle2 = "float(x) for x in torch.linspace(0, drop_path_rate, depth)"
                if needle2 in code:
                    eva_file.write_text(code.replace(needle2, replacement), encoding="utf-8")
                    logger.info("Patched %s: float(linspace) → pure Python", eva_file)
            # Invalidate bytecode
            pycache = eva_file.parent / "__pycache__"
            if pycache.is_dir():
                for f in pycache.glob("eva_model*.pyc"):
                    f.unlink()

    def _load_gemini(self) -> None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY env var not set")
        self._model = genai.Client(api_key=api_key)
        logger.info("Gemini Embedding client initialised (dim=%d)", self.get_dimension())

    # ── Public API ────────────────────────────────────────────────

    def get_dimension(self) -> int:
        # Both Jina CLIP v2 and gemini-embedding-2-preview produce 1024-dim vectors
        # — keeping them aligned avoids any DB migration when switching backends.
        return 1024

    # ── Fallback helpers ──────────────────────────────────────────

    def _fallback_to_jina(self, reason: str) -> None:
        """Switch this service from Gemini → local Jina after API failure."""
        logger.warning("Gemini embedding failed (%s) — falling back to local Jina CLIP v2.", reason)
        self._backend = "jina"
        self._model = None
        self._load_jina()

    # ── Text ──────────────────────────────────────────────────────

    def embed_text(self, text: str) -> list[float]:
        self._ensure_loaded()
        if self._backend == "jina":
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        try:
            return self._gemini_embed_text(text)
        except Exception as exc:
            self._fallback_to_jina(str(exc)[:120])
            return self.embed_text(text)

    def embed_batch_text(self, texts: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        if self._backend == "jina":
            vecs = self._model.encode(
                texts, normalize_embeddings=True, batch_size=32,
                show_progress_bar=len(texts) > 50,
            )
            return vecs.tolist()
        try:
            return self._gemini_embed_batch_text(texts)
        except Exception as exc:
            self._fallback_to_jina(str(exc)[:120])
            return self.embed_batch_text(texts)

    # ── Images ────────────────────────────────────────────────────

    def embed_image(self, image_path: str) -> list[float]:
        self._ensure_loaded()
        if self._backend == "jina":
            from PIL import Image

            img = Image.open(image_path).convert("RGB")
            vec = self._model.encode(img, normalize_embeddings=True)
            return vec.tolist()
        try:
            return self._gemini_embed_image(image_path)
        except Exception as exc:
            self._fallback_to_jina(str(exc)[:120])
            return self.embed_image(image_path)

    def embed_batch_images(self, paths: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        if self._backend == "jina":
            from PIL import Image

            imgs = [Image.open(p).convert("RGB") for p in paths]
            vecs = self._model.encode(
                imgs, normalize_embeddings=True, batch_size=8,
                show_progress_bar=len(imgs) > 10,
            )
            return vecs.tolist()
        try:
            return self._gemini_embed_batch_images(paths)
        except Exception as exc:
            self._fallback_to_jina(str(exc)[:120])
            return self.embed_batch_images(paths)

    # ── Gemini helpers ────────────────────────────────────────────

    def _gemini_embed_text(self, text: str) -> list[float]:
        from google.genai import types

        result = self._model.models.embed_content(
            model="gemini-embedding-2-preview",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=1024),
        )
        return list(result.embeddings[0].values)

    def _gemini_embed_batch_text(self, texts: list[str]) -> list[list[float]]:
        """Batch text embedding via single API call (chunked at 100/batch)."""
        from google.genai import types

        if not texts:
            return []
        out: list[list[float]] = []
        BATCH = 100  # Gemini embed_content per-request limit
        for i in range(0, len(texts), BATCH):
            chunk = texts[i : i + BATCH]
            result = self._model.models.embed_content(
                model="gemini-embedding-2-preview",
                contents=chunk,
                config=types.EmbedContentConfig(output_dimensionality=1024),
            )
            out.extend(list(e.values) for e in result.embeddings)
        return out

    def _gemini_embed_image(self, image_path: str) -> list[float]:
        from google.genai import types

        img_bytes = Path(image_path).read_bytes()
        mime = "image/jpeg"
        if image_path.lower().endswith(".png"):
            mime = "image/png"

        result = self._model.models.embed_content(
            model="gemini-embedding-2-preview",
            contents=[types.Part.from_bytes(data=img_bytes, mime_type=mime)],
            config=types.EmbedContentConfig(output_dimensionality=1024),
        )
        return list(result.embeddings[0].values)

    def _gemini_embed_batch_images(self, paths: list[str]) -> list[list[float]]:
        """Batch image embedding via single API call (chunked at 50/batch to stay under request size limits)."""
        from google.genai import types

        if not paths:
            return []
        out: list[list[float]] = []
        BATCH = 50  # smaller than text because images are heavier
        for i in range(0, len(paths), BATCH):
            chunk_paths = paths[i : i + BATCH]
            parts = []
            for p in chunk_paths:
                mime = "image/png" if p.lower().endswith(".png") else "image/jpeg"
                parts.append(
                    types.Part.from_bytes(data=Path(p).read_bytes(), mime_type=mime)
                )
            result = self._model.models.embed_content(
                model="gemini-embedding-2-preview",
                contents=parts,
                config=types.EmbedContentConfig(output_dimensionality=1024),
            )
            out.extend(list(e.values) for e in result.embeddings)
        return out
