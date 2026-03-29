"""Environment configuration for EduVidQA backend."""

from __future__ import annotations

import os


class Settings:
    """Application settings loaded from environment variables."""

    # API
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "7860"))

    # CORS — comma-separated allowed origins (default: allow all)
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # Model
    MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-VL-7B-Instruct")
    QUANTIZE_4BIT: bool = os.getenv("QUANTIZE_4BIT", "true").lower() == "true"

    # Data / cache
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./data/chroma")

    # Timeouts (seconds)
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "120"))

    # Lazy model loading: if True, model loads on first request instead of startup
    LAZY_LOAD: bool = os.getenv("LAZY_LOAD", "false").lower() == "true"


settings = Settings()
