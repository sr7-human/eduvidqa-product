"""Generate a comprehensive Lecture Digest from transcript + keyframes.

Uses Groq Llama 4 Scout (vision model) to produce a detailed digest that
captures every concept, formula, diagram, and example from the lecture.
The digest is saved to ``data/processed/{video_id}/digest.txt``.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DIGEST_PROMPT = """\
Create a detailed, comprehensive digest of this entire lecture.

This is NOT a summary — do NOT shorten or condense. Capture ALL:
- Key concepts explained
- Formulas, code, algorithms shown
- Diagrams and visual content described from the frames
- Examples given by the professor
- Important definitions and terminology

The transcript and lecture frames are provided below.
"""

# Groq has per-request image limits; send in batches of this size.
_IMAGES_PER_BATCH = 5


def generate_digest(
    video_id: str,
    data_dir: str = "data/processed",
    model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
) -> str:
    """Generate and save a comprehensive lecture digest.

    Returns the full digest text.
    Also saves to ``{data_dir}/{video_id}/digest.txt``.
    """
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY env var not set")

    client = Groq(api_key=api_key)
    base = Path(data_dir) / video_id

    # ── Load transcript ───────────────────────────────────────────
    transcript_path = base / "transcript" / "full.txt"
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    transcript = transcript_path.read_text(encoding="utf-8")

    # ── Load keyframe paths (sorted by timestamp) ─────────────────
    kf_dir = base / "keyframes"
    manifest_path = kf_dir / "manifest.json"
    kf_paths: list[Path] = []
    if manifest_path.is_file():
        import json

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Sort by timestamp
        manifest.sort(key=lambda x: x.get("timestamp", 0))
        for entry in manifest:
            p = Path(entry["file"])
            if p.is_file():
                kf_paths.append(p)
    else:
        # Fallback: glob JPEGs sorted by name
        kf_paths = sorted(kf_dir.glob("kf_*.jpg"))

    logger.info(
        "Digest: video=%s, transcript=%d chars, keyframes=%d",
        video_id,
        len(transcript),
        len(kf_paths),
    )

    # ── Small video: single-shot ──────────────────────────────────
    if len(kf_paths) <= _IMAGES_PER_BATCH:
        digest = _single_shot(client, model, transcript, kf_paths)
    else:
        # ── Large video: batched → merge ─────────────────────────
        digest = _batched_digest(client, model, transcript, kf_paths)

    # ── Save ──────────────────────────────────────────────────────
    out_path = base / "digest.txt"
    out_path.write_text(digest, encoding="utf-8")
    logger.info("Digest saved to %s (%d chars)", out_path, len(digest))
    return digest


# ── Internal helpers ──────────────────────────────────────────────


def _encode_image(path: Path) -> str:
    """Base64-encode an image file."""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _build_image_parts(paths: list[Path]) -> list[dict]:
    """Build Groq-style image content parts."""
    parts = []
    for p in paths:
        try:
            b64 = _encode_image(p)
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        except Exception as exc:
            logger.warning("Skipping keyframe %s: %s", p, exc)
    return parts


def _single_shot(
    client,
    model: str,
    transcript: str,
    kf_paths: list[Path],
) -> str:
    """Generate digest in a single API call."""
    user_content: list[dict] = [
        {"type": "text", "text": f"{_DIGEST_PROMPT}\n\nTRANSCRIPT:\n{transcript}"},
    ]
    user_content.extend(_build_image_parts(kf_paths))

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert educational content analyst."},
            {"role": "user", "content": user_content},
        ],
        max_tokens=8192,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def _batched_digest(
    client,
    model: str,
    transcript: str,
    kf_paths: list[Path],
) -> str:
    """Split keyframes into batches, generate partial digests, then merge."""
    # Split transcript roughly proportionally to keyframe batches
    n_batches = (len(kf_paths) + _IMAGES_PER_BATCH - 1) // _IMAGES_PER_BATCH
    words = transcript.split()
    words_per_batch = max(1, len(words) // n_batches)

    partial_digests: list[str] = []

    for batch_idx in range(n_batches):
        kf_start = batch_idx * _IMAGES_PER_BATCH
        kf_end = min(kf_start + _IMAGES_PER_BATCH, len(kf_paths))
        batch_kfs = kf_paths[kf_start:kf_end]

        w_start = batch_idx * words_per_batch
        w_end = (
            len(words) if batch_idx == n_batches - 1 else (batch_idx + 1) * words_per_batch
        )
        batch_transcript = " ".join(words[w_start:w_end])

        logger.info(
            "Digest batch %d/%d: %d keyframes, %d words",
            batch_idx + 1,
            n_batches,
            len(batch_kfs),
            w_end - w_start,
        )

        user_content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"Part {batch_idx + 1}/{n_batches} of the lecture.\n\n"
                    f"{_DIGEST_PROMPT}\n\nTRANSCRIPT PORTION:\n{batch_transcript}"
                ),
            },
        ]
        user_content.extend(_build_image_parts(batch_kfs))

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert educational content analyst."},
                {"role": "user", "content": user_content},
            ],
            max_tokens=4096,
            temperature=0.3,
        )
        partial_digests.append(resp.choices[0].message.content.strip())

    # ── Merge partials into one coherent digest ──────────────────
    combined = "\n\n---\n\n".join(partial_digests)
    merge_prompt = (
        "Below are partial digests of a single lecture, generated in order. "
        "Merge them into ONE comprehensive, coherent digest. "
        "Do NOT lose any details — combine, de-duplicate, and organise.\n\n"
        f"{combined}"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert educational content analyst."},
            {"role": "user", "content": merge_prompt},
        ],
        max_tokens=8192,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()
