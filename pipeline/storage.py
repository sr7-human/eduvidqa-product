"""Helpers for uploading lecture keyframes to Supabase Storage.

The ``keyframes`` bucket is public-read so any backend (local dev, HF Spaces,
etc.) can fetch frames by URL — survives Docker rebuilds and ephemeral disks.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

BUCKET = "keyframes"


def _client():
    """Lazily build a Supabase service-role client. Returns None if creds missing."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        logger.warning("Supabase URL/SERVICE_ROLE_KEY not set — keyframe uploads disabled")
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase client init failed: %s", exc)
        return None


def _public_url(client, object_path: str) -> str:
    return client.storage.from_(BUCKET).get_public_url(object_path)


def upload_keyframe(video_id: str, kf: dict) -> str | None:
    """Upload a single keyframe JPEG; return its public URL or None on failure."""
    client = _client()
    if client is None:
        return None
    src = Path(kf["file"])
    if not src.is_file():
        logger.warning("Keyframe file missing locally: %s", src)
        return None
    object_path = f"{video_id}/{src.name}"
    try:
        client.storage.from_(BUCKET).upload(
            object_path,
            src.read_bytes(),
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        return _public_url(client, object_path)
    except Exception as exc:  # noqa: BLE001
        # Most "duplicate" errors mean the file is already there — fetch its URL.
        msg = str(exc).lower()
        if "duplicate" in msg or "already exists" in msg or "resource already exists" in msg:
            return _public_url(client, object_path)
        logger.warning("Upload failed for %s: %s", object_path, exc)
        return None


def upload_keyframe_batch(video_id: str, kfs: Iterable[dict]) -> list[str | None]:
    """Upload many keyframes; returns list of public URLs aligned to the input order.

    Falls back to the local file path string for any upload that fails so the
    caller can still record *something*.
    """
    client = _client()
    if client is None:
        return [None] * len(list(kfs))

    out: list[str | None] = []
    for kf in kfs:
        out.append(upload_keyframe(video_id, kf))
    return out
