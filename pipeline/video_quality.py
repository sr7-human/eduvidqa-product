"""Video-quality presets: map a human-chosen (or AI-suggested) video *type* to
the keyframe download resolution.

The keyframe images are extracted at the native resolution of the downloaded
video, so the *only* knob that controls keyframe sharpness is the download
height cap. Different lecture styles need different sharpness:

* A handheld camera panning across a distant whiteboard needs high resolution
  (the writing is small in the frame).
* A fixed screen-share / slides / picture-in-picture professor is already
  readable at a lower resolution (the content fills the frame).
* Pure animation is clean and large, so a low resolution is plenty.

Density (how MANY frames) is handled automatically by the SSIM de-duplication
in ``pipeline/keyframes.py`` — a static slide keeps very few frames on its own —
so this module only decides resolution.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Presets ─────────────────────────────────────────────────────────────
# key → (label, max_height, help text)
QUALITY_PRESETS: dict[str, dict] = {
    "auto": {
        "label": "Standard lecture (720p)",
        "max_height": 720,
        "help": "Good default. Teacher + board/slides, readable text.",
    },
    "handheld": {
        "label": "Handheld / moving camera (1080p)",
        "max_height": 1080,
        "help": "Camera pans around, board is distant or small in frame — needs the sharpest frames.",
    },
    "slides": {
        "label": "Slides / screen-share / PiP professor (480p)",
        "max_height": 480,
        "help": "Screen is fixed and fills the frame — readable even at lower resolution. Saves storage.",
    },
    "animation": {
        "label": "Pure animation (360p)",
        "max_height": 360,
        "help": "Clean, large animated visuals — lowest resolution is plenty.",
    },
}

DEFAULT_TYPE = "auto"


def max_height_for(video_type: str | None) -> int:
    """Return the download height cap for a preset key (falls back to default)."""
    preset = QUALITY_PRESETS.get((video_type or "").strip().lower())
    if not preset:
        preset = QUALITY_PRESETS[DEFAULT_TYPE]
    return int(preset["max_height"])


def format_for_height(max_height: int) -> str:
    """Build the yt-dlp format string for a given height cap.

    Prefers a separate video+audio muxed to mp4 at/below the cap, then falls
    back progressively so a download never fails just because one exact format
    is missing.
    """
    h = int(max_height)
    return (
        f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={h}]+bestaudio/"
        f"best[height<={h}]/best"
    )


# ── Optional AI suggestion ──────────────────────────────────────────────

_SUGGEST_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_SUGGEST_PROMPT = (
    "You are shown a few frames sampled from a lecture video. Classify the video "
    "into EXACTLY ONE of these types and reply with ONLY the type keyword:\n"
    "- handheld  : a real camera films a room; the whiteboard/blackboard is "
    "distant or small in the frame; the presenter moves around.\n"
    "- slides    : a fixed screen-share, slides, or a screen with a small "
    "picture-in-picture presenter; the content area is fixed and fills most of "
    "the frame.\n"
    "- animation : purely animated/drawn visuals, no real classroom.\n"
    "- auto      : a normal lecture that doesn't clearly fit the above.\n"
    "Reply with only one word: handheld, slides, animation, or auto."
)


def suggest_video_type(video_id: str, groq_api_key: str | None) -> tuple[str, str]:
    """Sample a few frames and ask a vision model to guess the video type.

    Returns ``(type_key, note)``. On any failure returns ``("auto", <reason>)``
    so the caller can safely fall back to the default preset.
    """
    if not groq_api_key:
        return DEFAULT_TYPE, "no Groq key — using default"
    try:
        frames = _sample_frames(video_id, n=3)
    except Exception as exc:  # noqa: BLE001
        return DEFAULT_TYPE, f"frame sampling failed ({str(exc)[:60]})"
    if not frames:
        return DEFAULT_TYPE, "could not sample frames"
    try:
        import base64

        from groq import Groq

        content: list[dict] = [{"type": "text", "text": _SUGGEST_PROMPT}]
        for fp in frames:
            with open(fp, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            )
        client = Groq(api_key=groq_api_key)
        resp = client.chat.completions.create(
            model=_SUGGEST_MODEL,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=8,
        )
        raw = (resp.choices[0].message.content or "").strip().lower()
        for key in QUALITY_PRESETS:
            if key in raw:
                return key, f"AI suggested: {key}"
        return DEFAULT_TYPE, f"AI unclear ('{raw[:20]}') — using default"
    except Exception as exc:  # noqa: BLE001
        return DEFAULT_TYPE, f"AI call failed ({str(exc)[:60]})"
    finally:
        for fp in frames:
            try:
                import os

                os.remove(fp)
            except Exception:
                pass


def _sample_frames(video_id: str, n: int = 3) -> list[str]:
    """Download a few 360p frames spread across the video for classification."""
    import subprocess
    import tempfile
    from pathlib import Path

    import yt_dlp

    from pipeline.ingest import get_cookie_ydl_opts

    url = f"https://www.youtube.com/watch?v={video_id}"
    # Duration (cheap metadata call)
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                           **get_cookie_ydl_opts()}) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    duration = int(info.get("duration") or 0)
    if duration <= 0:
        return []

    # Pick n timestamps at even fractions (avoid the very start/end)
    fracs = [(i + 1) / (n + 1) for i in range(n)]
    stamps = [max(5, int(duration * f)) for f in fracs]

    out: list[str] = []
    for ts in stamps:
        wd = Path(tempfile.mkdtemp(prefix="eduvidqa-vqsuggest-"))
        slice_path = wd / "s.mp4"
        opts = {
            "format": "136/bestvideo[height<=360]/best[height<=360]/best/worst",
            "outtmpl": str(slice_path),
            "quiet": True,
            "no_warnings": True,
            "no_playlist": True,
            "download_ranges": (lambda s: (lambda info, ydl: [{"start_time": s, "end_time": s + 2}]))(ts),
            "force_keyframes_at_cuts": True,
            **get_cookie_ydl_opts(),
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            cand = sorted(wd.glob("s*"), key=lambda p: p.stat().st_size, reverse=True)
            if not cand:
                continue
            jpg = wd / f"f_{ts}.jpg"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(cand[0]),
                 "-frames:v", "1", "-q:v", "5", str(jpg)],
                capture_output=True, timeout=15,
            )
            if jpg.exists() and jpg.stat().st_size > 0:
                out.append(str(jpg))
        except Exception as exc:  # noqa: BLE001
            logger.warning("sample frame at %ds failed: %s", ts, str(exc)[:80])
    return out
