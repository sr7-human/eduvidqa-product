"""Per-user daily LLM request counter.

Passive bookkeeping — records each LLM call our pipelines make, attributed to
the current user (set by the backend's request-scoped context as the
``EDUVIDQA_USER_ID`` env var). This makes NO extra API calls, so it has ZERO
effect on provider rate limits/quota — it just lets us show the user how many
requests they've spent today against the free-tier caps.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def record(provider: str, model: str) -> None:
    """Increment today's call count for (current user, provider, model). Best-effort."""
    uid = os.getenv("EDUVIDQA_USER_ID", "").strip()
    url = os.getenv("DATABASE_URL", "").strip()
    if not uid or not url:
        return
    try:
        import psycopg2

        conn = psycopg2.connect(url)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_usage (user_id, day, provider, model, count)
                    VALUES (%s::uuid, CURRENT_DATE, %s, %s, 1)
                    ON CONFLICT (user_id, day, provider, model)
                    DO UPDATE SET count = llm_usage.count + 1
                    """,
                    (uid, provider, str(model)[:80]),
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.debug("usage.record failed: %s", exc)


def record_rate_limit(service: str, detail: str = "") -> None:
    """Mark a provider key as rate-limited/quota-exhausted for the current user
    (so the UI can show a persistent indicator beside the key). Best-effort."""
    uid = os.getenv("EDUVIDQA_USER_ID", "").strip()
    url = os.getenv("DATABASE_URL", "").strip()
    if not uid or not url:
        return
    try:
        import psycopg2

        conn = psycopg2.connect(url)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO key_health (user_id, service, rate_limited_at, detail)
                    VALUES (%s::uuid, %s, now(), %s)
                    ON CONFLICT (user_id, service)
                    DO UPDATE SET rate_limited_at = now(), detail = EXCLUDED.detail
                    """,
                    (uid, service, str(detail)[:200]),
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.debug("usage.record_rate_limit failed: %s", exc)
