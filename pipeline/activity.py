"""In-memory ring buffer of recent external API calls (LLM providers, etc.).

Lets the UI show a LIVE feed of what the pipeline is doing — which provider/model
was called, whether it succeeded or was rate-limited, and how long it took — so a
"stuck" ingest is legible instead of a frozen progress bar.

Best-effort + thread-safe; never raises into the caller.
"""
from __future__ import annotations

import threading
import time
from collections import deque

_MAX_EVENTS = 120
_LOCK = threading.Lock()
_EVENTS: deque[dict] = deque(maxlen=_MAX_EVENTS)
_SEQ = 0


def record_activity(provider: str, model: str, purpose: str,
                    status: str, ms: float | None = None, detail: str = "") -> None:
    """Append one activity event. ``status`` is e.g. 'ok' | 'rate_limited' | 'error'."""
    global _SEQ
    try:
        with _LOCK:
            _SEQ += 1
            _EVENTS.append({
                "seq": _SEQ,
                "ts": time.time(),
                "provider": provider,
                "model": model or "",
                "purpose": purpose or "",
                "status": status,
                "ms": round(ms) if ms is not None else None,
                "detail": (detail or "")[:160],
            })
    except Exception:  # noqa: BLE001 — telemetry must never break the pipeline
        pass


def get_activity(since_seq: int = 0) -> list[dict]:
    """Return events with seq > ``since_seq`` (oldest first)."""
    with _LOCK:
        return [e for e in _EVENTS if e["seq"] > since_seq]
