"""Per-feature LLM model overrides.

The backend's request-scoped context (``_ScopedAPIKeys``) injects the user's
saved model preferences into ``os.environ`` as ``EDUVIDQA_MODEL_<FEATURE>``
values of the form ``"provider:model"`` (or ``"auto"``). The pipelines read
these via the helpers below so a user can choose which model powers each
feature (answers / quizzes / digest) without threading args everywhere.

Falls back to the built-in defaults when unset or ``auto``.
"""
from __future__ import annotations

import os

# Built-in defaults per feature: (provider, model)
# gemini-flash-latest is an ALIAS Google keeps pointed at the current flash model,
# so it never gets deprecated out from under us (gemini-2.5-flash was retired).
DEFAULTS: dict[str, tuple[str, str]] = {
    "answers": ("gemini", "gemini-flash-latest"),
    "quizzes": ("gemini", "gemini-flash-latest"),
    "digest": ("gemini", "gemini-flash-latest"),
}

VALID_FEATURES = set(DEFAULTS)
VALID_PROVIDERS = {"gemini", "openrouter", "groq"}

# Free OpenRouter models (0 credit cost) to try, in order, when OpenRouter is
# used as a fallback on a $0-credit key. Free models are heavily shared and
# 429-rate-limit often, so we try several, then fall back to the cheap paid
# model which works under light load.
OR_FREE_TEXT_MODELS = [
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
]
OR_TEXT_PAID_FALLBACK = "deepseek/deepseek-chat"

OR_FREE_VISION_MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]
OR_VISION_PAID_FALLBACK = "meta-llama/llama-3.2-11b-vision-instruct"


def resolve(feature: str) -> tuple[str | None, str | None]:
    """Return (provider, model) override for a feature, or (None, None) if the
    user left it on 'auto' / unset."""
    raw = os.getenv(f"EDUVIDQA_MODEL_{feature.upper()}", "").strip()
    if not raw or raw.lower() == "auto":
        return None, None
    if ":" in raw:
        provider, model = raw.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        return (provider if provider in VALID_PROVIDERS else None), (model or None)
    return None, raw.strip() or None


def gemini_model(feature: str, default: str = "gemini-flash-latest") -> str:
    """Model name to use for a Gemini call for ``feature`` (or the default)."""
    provider, model = resolve(feature)
    if provider == "gemini" and model:
        return model
    return default


def openrouter_override(feature: str) -> str | None:
    """If the user explicitly picked an OpenRouter model for ``feature``,
    return that model id so the pipeline can try OpenRouter first; else None."""
    provider, model = resolve(feature)
    if provider == "openrouter" and model:
        return model
    return None
