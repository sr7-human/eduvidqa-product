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
