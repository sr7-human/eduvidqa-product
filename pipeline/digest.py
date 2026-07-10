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

from pipeline.model_prefs import gemini_model

logger = logging.getLogger(__name__)

_DIGEST_PROMPT = """\
Create a detailed, comprehensive digest of this entire lecture.

This is NOT a summary — do NOT shorten or condense. Capture ALL:
- Key concepts explained
- Formulas, code, algorithms shown
- Diagrams and visual content described from the frames
- Examples given by the professor
- Important definitions and terminology

Pedagogy — while capturing everything, teach it well:
- Preserve the DEEP STRUCTURAL LOGIC of each idea while abstracting away the \
non-essential clutter, so as to remove the initial cognitive load.
- Add REAL-LIFE ANALOGIES that a complete layman could picture for the harder \
concepts.
- For key jargon/technical terms, give a brief ETYMOLOGICAL BREAKDOWN of the \
word's roots so the name itself reinforces the meaning.

The transcript and lecture frames are provided below.
"""

# Groq has per-request image limits; send in batches of this size.
_IMAGES_PER_BATCH = 5


def generate_digest(
    video_id: str,
    data_dir: str = "data/processed",
    model: str | None = None,
) -> str:
    """Generate and save a comprehensive lecture digest.

    Uses **Gemini** (vision) by default — generous free tier + large context,
    so it takes many keyframes in one call. Falls back to Groq Llama-4 Scout
    if Gemini is unavailable or ``INFERENCE_ENGINE=groq``.

    Returns the full digest text. Also saves to ``{data_dir}/{video_id}/digest.txt``.
    """
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

    # ── Choose engine: Gemini is the default ──────────────────────
    engine = (os.getenv("INFERENCE_ENGINE") or "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")

    if gemini_key and engine != "groq":
        digest = _gemini_digest(transcript, kf_paths, gemini_key, model=gemini_model("digest"))
    elif groq_key:
        from groq import Groq

        client = Groq(api_key=groq_key)
        groq_model = model or "meta-llama/llama-4-scout-17b-16e-instruct"
        if len(kf_paths) <= _IMAGES_PER_BATCH:
            digest = _single_shot(client, groq_model, transcript, kf_paths)
        else:
            digest = _batched_digest(client, groq_model, transcript, kf_paths)
    else:
        raise RuntimeError("No LLM key set (need GEMINI_API_KEY or GROQ_API_KEY)")

    # ── Save ──────────────────────────────────────────────────────
    out_path = base / "digest.txt"
    out_path.write_text(digest, encoding="utf-8")
    logger.info("Digest saved to %s (%d chars)", out_path, len(digest))
    return digest


def _gemini_digest(
    transcript: str,
    kf_paths: list[Path],
    api_key: str,
    model: str = "gemini-flash-latest",
    max_images: int = 60,
) -> str:
    """Generate the digest with Gemini vision (transcript + sampled keyframes).

    Samples up to ``max_images`` keyframes evenly — the digest needs
    representative frames, not every single one.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    if len(kf_paths) > max_images:
        step = len(kf_paths) / max_images
        sampled = [kf_paths[int(i * step)] for i in range(max_images)]
    else:
        sampled = kf_paths

    parts = [types.Part.from_text(text=f"{_DIGEST_PROMPT}\n\nTRANSCRIPT:\n{transcript}")]
    for p in sampled:
        try:
            parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type="image/jpeg"))
        except Exception as exc:
            logger.warning("Skipping keyframe %s: %s", p, exc)

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return (response.text or "").strip()


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
