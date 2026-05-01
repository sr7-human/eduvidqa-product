"""Environment configuration for EduVidQA backend."""

from __future__ import annotations

import os
from pathlib import Path

# Load .env from project root before reading any env vars
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed — env vars must be set externally


class Settings:
    """Application settings loaded from environment variables."""

    # API
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "7860"))

    # CORS — comma-separated allowed origins (default: local Vite dev server only)
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # Model — default to 3B for M2 Mac (7B needs CUDA 4-bit)
    MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-VL-3B-Instruct")
    QUANTIZE_4BIT: bool = os.getenv("QUANTIZE_4BIT", "true").lower() == "true"

    # Mock mode — return dummy answers without loading the model
    MOCK_INFERENCE: bool = os.getenv("MOCK_INFERENCE", "false").lower() == "true"

    # Inference engine: "local" (Qwen on device), "groq" (free API), or "gemini" (best quality)
    INFERENCE_ENGINE: str = os.getenv("INFERENCE_ENGINE", "local")

    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Quality evaluation method: "hf_inference", "groq", or "local"
    EVAL_METHOD: str = os.getenv("EVAL_METHOD", "hf_inference")

    # Data / cache
    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    CHROMA_DIR: str = os.getenv("CHROMA_DIR", "./data/chroma")

    # Timeouts (seconds)
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "120"))

    # Lazy model loading: if True, model loads on first request instead of startup
    LAZY_LOAD: bool = os.getenv("LAZY_LOAD", "false").lower() == "true"


settings = Settings()
