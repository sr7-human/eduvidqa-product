"""Durable, fenced ownership for video ingest workers.

A video can have many resume attempts, but only one active owner. Every mutation
includes the claim's owner token and attempt number, so an expired process cannot
overwrite a newer worker after lease takeover. Backed by the ``video_ingest_jobs``
table. All behaviour here is inert unless ``DURABLE_JOBS_V1`` is enabled by the
caller — this module only provides the primitives.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Thread
from typing import Iterator

import psycopg2

DEFAULT_LEASE_SECONDS = 120

# Canonical ingest stage order. Resume runs the first incomplete stage onward.
INGEST_STAGES = (
    "transcript",
    "transcript_embedding",
    "download",
    "keyframes",
    "digest",
    "keyframe_embedding",
    "checkpoints",
    "chapters",
    "ready",
)


def should_run_stage(start_stage: str, stage: str) -> bool:
    """Return whether *stage* is at or after the first incomplete stage."""
    try:
        return INGEST_STAGES.index(stage) >= INGEST_STAGES.index(start_stage)
    except ValueError as exc:
        raise ValueError(f"Unknown ingest stage: {exc.args[0]}") from exc


class LeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the durable ingest job."""


@dataclass(frozen=True)
class JobLease:
    video_id: str
    pipeline_version: int
    owner_token: str
    attempt: int
    next_stage: str


_current_lease: ContextVar[JobLease | None] = ContextVar(
    "eduvidqa_ingest_job_lease",
    default=None,
)


def current_job_lease() -> JobLease | None:
    return _current_lease.get()


@contextmanager
def use_job_lease(lease: JobLease) -> Iterator[JobLease]:
    token: Token = _current_lease.set(lease)
    try:
        yield lease
    finally:
        _current_lease.reset(token)


def _database_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    from backend.supabase_config import get_database_url

    return get_database_url()


@contextmanager
def maintain_lease(
    lease: JobLease,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    database_url: str | None = None,
) -> Iterator[JobLease]:
    """Renew a lease while a long blocking pipeline stage is running."""
    stopped = Event()
    lost = Event()
    interval = max(1.0, lease_seconds / 3)

    def renew() -> None:
        while not stopped.wait(interval):
            try:
                if not heartbeat(lease, lease_seconds=lease_seconds, database_url=database_url):
                    lost.set()
                    return
            except Exception:
                # A transient DB outage should not immediately kill expensive
                # work. The next fenced write will reject a stale owner anyway.
                continue

    thread = Thread(target=renew, name=f"ingest-heartbeat-{lease.video_id}", daemon=True)
    thread.start()
    try:
        yield lease
        if lost.is_set():
            raise LeaseLostError(f"Lost ingest lease for {lease.video_id}")
    finally:
        stopped.set()
        thread.join(timeout=2.0)


def claim_job(
    video_id: str,
    *,
    pipeline_version: int = 1,
    start_stage: str = "transcript",
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    database_url: str | None = None,
) -> JobLease | None:
    """Atomically claim a queued/paused/failed or expired-running job.

    Returns ``None`` while another live owner holds the lease or after the job
    is complete. A single ``INSERT .. ON CONFLICT .. DO UPDATE .. WHERE`` makes
    creation, stale takeover, and duplicate-request rejection one operation.
    """
    owner_token = str(uuid.uuid4())
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO video_ingest_jobs (
                video_id, pipeline_version, state, next_stage, attempt,
                owner_token, lease_expires_at, heartbeat_at, updated_at
            )
            VALUES (
                %s, %s, 'running', %s, 1,
                %s::uuid, now() + (%s * interval '1 second'), now(), now()
            )
            ON CONFLICT (video_id, pipeline_version) DO UPDATE
            SET state = 'running',
                attempt = video_ingest_jobs.attempt + 1,
                owner_token = EXCLUDED.owner_token,
                lease_expires_at = EXCLUDED.lease_expires_at,
                heartbeat_at = now(),
                last_error = NULL,
                retry_after = NULL,
                updated_at = now()
            WHERE (
                    video_ingest_jobs.state IN ('queued', 'paused', 'failed')
                    AND (
                        video_ingest_jobs.retry_after IS NULL
                        OR video_ingest_jobs.retry_after <= now()
                    )
                  )
               OR (
                    video_ingest_jobs.state = 'running'
                    AND (
                        video_ingest_jobs.lease_expires_at IS NULL
                        OR video_ingest_jobs.lease_expires_at <= now()
                    )
                  )
            RETURNING attempt, next_stage
            """,
            (video_id, pipeline_version, start_stage, owner_token, lease_seconds),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return JobLease(
        video_id=video_id,
        pipeline_version=pipeline_version,
        owner_token=owner_token,
        attempt=int(row[0]),
        next_stage=str(row[1]),
    )


def heartbeat(
    lease: JobLease,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    database_url: str | None = None,
) -> bool:
    """Extend an active lease. False means ownership was lost."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE video_ingest_jobs
            SET heartbeat_at = now(),
                lease_expires_at = now() + (%s * interval '1 second'),
                updated_at = now()
            WHERE video_id = %s AND pipeline_version = %s
              AND state = 'running' AND owner_token = %s::uuid AND attempt = %s
            """,
            (lease_seconds, lease.video_id, lease.pipeline_version, lease.owner_token, lease.attempt),
        )
        return cur.rowcount == 1


def advance_stage(
    lease: JobLease,
    next_stage: str,
    *,
    completed_items: int = 0,
    total_items: int = 0,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    database_url: str | None = None,
) -> bool:
    """Commit a durable stage/cursor update and renew the lease."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE video_ingest_jobs
            SET next_stage = %s,
                completed_items = %s,
                total_items = %s,
                heartbeat_at = now(),
                lease_expires_at = now() + (%s * interval '1 second'),
                updated_at = now()
            WHERE video_id = %s AND pipeline_version = %s
              AND state = 'running' AND owner_token = %s::uuid AND attempt = %s
            """,
            (
                next_stage,
                max(0, int(completed_items)),
                max(0, int(total_items)),
                lease_seconds,
                lease.video_id,
                lease.pipeline_version,
                lease.owner_token,
                lease.attempt,
            ),
        )
        return cur.rowcount == 1


def update_video_status(
    lease: JobLease,
    status: str,
    detail: str | None = None,
    *,
    database_url: str | None = None,
) -> bool:
    """Update the legacy videos projection only while this lease is current."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE videos v
            SET status = %s, status_detail = %s, updated_at = now()
            FROM video_ingest_jobs j
            WHERE v.video_id = %s AND v.pipeline_version = %s
              AND j.video_id = v.video_id AND j.pipeline_version = v.pipeline_version
              AND j.state = 'running' AND j.owner_token = %s::uuid AND j.attempt = %s
            """,
            (status, detail, lease.video_id, lease.pipeline_version, lease.owner_token, lease.attempt),
        )
        return cur.rowcount == 1


def update_video_progress(
    lease: JobLease,
    step: str,
    pct: int | None = None,
    detail: str | None = None,
    *,
    database_url: str | None = None,
) -> bool:
    """Update legacy progress JSON only while this lease is current."""
    payload = json.dumps({
        "step": step,
        "pct": pct,
        "detail": detail,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE videos v
            SET progress = %s::jsonb, updated_at = now()
            FROM video_ingest_jobs j
            WHERE v.video_id = %s AND v.pipeline_version = %s
              AND j.video_id = v.video_id AND j.pipeline_version = v.pipeline_version
              AND j.state = 'running' AND j.owner_token = %s::uuid AND j.attempt = %s
            """,
            (payload, lease.video_id, lease.pipeline_version, lease.owner_token, lease.attempt),
        )
        return cur.rowcount == 1


def complete_job(lease: JobLease, *, database_url: str | None = None) -> bool:
    """Mark the current attempt complete and release ownership."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE video_ingest_jobs
            SET state = 'complete', next_stage = 'ready', owner_token = NULL,
                lease_expires_at = NULL, heartbeat_at = now(),
                last_error = NULL, retry_after = NULL, updated_at = now()
            WHERE video_id = %s AND pipeline_version = %s
              AND state = 'running' AND owner_token = %s::uuid AND attempt = %s
            """,
            (lease.video_id, lease.pipeline_version, lease.owner_token, lease.attempt),
        )
        return cur.rowcount == 1


def fail_job(
    lease: JobLease,
    error: str,
    *,
    retry_after: datetime | None = None,
    database_url: str | None = None,
) -> bool:
    """Persist failure details and release ownership for a future retry."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE video_ingest_jobs
            SET state = 'failed', owner_token = NULL, lease_expires_at = NULL,
                heartbeat_at = now(), last_error = %s, retry_after = %s, updated_at = now()
            WHERE video_id = %s AND pipeline_version = %s
              AND state = 'running' AND owner_token = %s::uuid AND attempt = %s
            """,
            (str(error)[:2000], retry_after, lease.video_id, lease.pipeline_version, lease.owner_token, lease.attempt),
        )
        return cur.rowcount == 1


def pause_job(
    lease: JobLease,
    detail: str = "",
    *,
    retry_after: datetime | None = None,
    database_url: str | None = None,
) -> bool:
    """Pause safely at the last committed stage and release ownership."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE video_ingest_jobs
            SET state = 'paused', owner_token = NULL, lease_expires_at = NULL,
                heartbeat_at = now(), last_error = NULLIF(%s, ''), retry_after = %s, updated_at = now()
            WHERE video_id = %s AND pipeline_version = %s
              AND state = 'running' AND owner_token = %s::uuid AND attempt = %s
            """,
            (str(detail)[:2000], retry_after, lease.video_id, lease.pipeline_version, lease.owner_token, lease.attempt),
        )
        return cur.rowcount == 1


def get_job(video_id: str, *, pipeline_version: int = 1, database_url: str | None = None) -> dict | None:
    """Return non-secret job status for API/UI projection and diagnostics."""
    with psycopg2.connect(_database_url(database_url)) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT state, next_stage, completed_items, total_items, attempt,
                   lease_expires_at, heartbeat_at, last_error, retry_after,
                   created_at, updated_at
            FROM video_ingest_jobs
            WHERE video_id = %s AND pipeline_version = %s
            """,
            (video_id, pipeline_version),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "state": row[0],
        "next_stage": row[1],
        "completed_items": row[2],
        "total_items": row[3],
        "attempt": row[4],
        "lease_expires_at": row[5],
        "heartbeat_at": row[6],
        "last_error": row[7],
        "retry_after": row[8],
        "created_at": row[9],
        "updated_at": row[10],
    }
