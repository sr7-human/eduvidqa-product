# Session I — Auth Middleware + Background Worker + Rate Limiting

## Status: ✅ COMPLETE
## Dependencies: G ✅ (Supabase Auth configured), H1 ✅ (pgvector rag.py)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

The API has NO authentication — anyone can hit `/api/ask` and burn paid LLM tokens. This session adds:
1. Supabase JWT verification on protected endpoints
2. Background worker for heavy video ingest (currently blocks HTTP for 30-120s)
3. Rate limiting via `slowapi`
4. A status polling endpoint + user-video tracking + user library endpoint

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`  
**Start backend:** `uvicorn backend.app:app --reload --port 8000`

---

## Current backend/app.py Structure (354 lines)

```
Endpoints:
  GET  /api/health         — public, returns system status
  POST /api/process-video  — downloads + ingests video SYNCHRONOUSLY (blocks 30-120s)
  POST /api/ask            — retrieves + generates answer (~3s cached)

Key imports:
  from backend.config import settings
  from backend.models import AskRequest, AskResponse, HealthResponse, ProcessRequest, ProcessResponse, ...
  from pipeline.rag import LectureIndex
  from pipeline.ingest import parse_video_id
```

**Current `backend/config.py`** has:
- `CORS_ORIGINS`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `DATA_DIR`, `CHROMA_DIR`, `LAZY_LOAD`
- No Supabase JWT secret yet

**Current `backend/supabase_config.py`** has:
- `get_supabase_client()` — uses `SUPABASE_SERVICE_ROLE_KEY`
- `get_database_url()` — uses `DATABASE_URL`

**`.env`** has: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `SUPABASE_JWT_SECRET`

---

## Task 1: Create Auth Middleware

**Create file:** `backend/auth.py`

```python
"""Supabase JWT verification for FastAPI."""
import os
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

def _get_jwt_secret() -> str:
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET must be set in .env")
    return secret

async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """Verify Supabase JWT. Returns decoded payload or None if no token."""
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            _get_jwt_secret(),
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_auth(token: dict | None = Depends(verify_token)) -> str:
    """Returns user_id or raises 401."""
    if token is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token["sub"]

async def optional_auth(token: dict | None = Depends(verify_token)) -> str | None:
    """Returns user_id or None (for demo/unauthenticated access)."""
    return token.get("sub") if token else None
```

**Install:** `pip install PyJWT` — add `PyJWT` to `requirements.txt`.

---

## Task 2: Protect Endpoints in backend/app.py

### 2a. Add imports at top of app.py:
```python
from backend.auth import require_auth, optional_auth
from fastapi import BackgroundTasks, Depends
import psycopg2
```

### 2b. `/api/health` — stays public (no change needed)

### 2c. `/api/ask` — optional auth, demo video allowed without login:

Replace the current `ask_question` function signature with:
```python
DEMO_VIDEO_ID = "3OmfTIf-SOU"

@app.post("/api/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    raw_request: Request,
    user_id: str | None = Depends(optional_auth),
) -> AskResponse:
    """Full pipeline: URL + question + timestamp → AI answer."""
    video_id = ...  # existing parse_video_id logic
    
    # Unauthenticated → only demo video allowed
    if user_id is None and video_id != DEMO_VIDEO_ID:
        raise HTTPException(status_code=401, detail="Sign in to ask questions on this video")
    
    # If authenticated, track user-video
    if user_id:
        _link_user_video(user_id, video_id)
    
    # ... rest of existing code stays the same ...
```

### 2d. `/api/process-video` — require auth + background worker:

Replace the current synchronous `process_video` with:
```python
@app.post("/api/process-video")
async def process_video(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_auth),
):
    try:
        video_id = parse_video_id(request.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    index = _get_index()

    # Already indexed?
    if index.is_indexed(video_id):
        _link_user_video(user_id, video_id)
        return {"video_id": video_id, "status": "ready", "message": "Already indexed"}

    # Already processing?
    status = _get_video_status(video_id)
    if status == "processing":
        return {"video_id": video_id, "status": "processing", "message": "Already being processed"}

    # Register + queue background work
    _register_video(video_id)
    background_tasks.add_task(_ingest_video_bg, video_id, request.youtube_url, user_id)
    return {"video_id": video_id, "status": "processing", "message": "Processing started"}
```

Move ALL the existing heavy ingest logic into a background function:
```python
def _ingest_video_bg(video_id: str, youtube_url: str, user_id: str):
    """Background ingest — runs in a thread via FastAPI BackgroundTasks."""
    try:
        _update_video_status(video_id, "processing")
        
        # === Move all existing process_video body here ===
        # Step 1: Download video
        # Step 2: Extract keyframes
        # Step 3: Chunk transcript
        # Step 4: Generate digest
        # Step 5: Index in pgvector
        # Step 6: Delete .mp4
        
        _update_video_status(video_id, "ready")
        _link_user_video(user_id, video_id)
    except Exception as e:
        logger.exception(f"Ingest failed for {video_id}")
        _update_video_status(video_id, "failed", str(e)[:500])
```

---

## Task 3: Add DB Helper Functions

Add these to `backend/app.py` (or a separate `backend/db.py`):

```python
def _get_db_url():
    from backend.supabase_config import get_database_url
    return get_database_url()

def _register_video(video_id: str):
    """Insert pending video row. Idempotent."""
    import uuid
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO videos (id, video_id, pipeline_version, status)
            VALUES (%s, %s, 1, 'pending')
            ON CONFLICT (video_id, pipeline_version) DO NOTHING
        """, (str(uuid.uuid4()), video_id))
    conn.commit(); conn.close()

def _get_video_status(video_id: str) -> str | None:
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM videos WHERE video_id = %s", (video_id,))
        row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def _update_video_status(video_id: str, status: str, detail: str = None):
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE videos SET status = %s, status_detail = %s, updated_at = now()
            WHERE video_id = %s
        """, (status, detail, video_id))
    conn.commit(); conn.close()

def _link_user_video(user_id: str, video_id: str):
    """Track that this user has used this video."""
    if not user_id:
        return
    import uuid
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO user_videos (id, user_id, video_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, video_id)
            DO UPDATE SET last_watched_at = now()
        """, (str(uuid.uuid4()), user_id, video_id))
    conn.commit(); conn.close()
```

---

## Task 4: Status Polling Endpoint

Add to `backend/app.py`:
```python
@app.get("/api/videos/{video_id}/status")
async def video_status(video_id: str):
    """Frontend polls this while video is processing."""
    status = _get_video_status(video_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"video_id": video_id, "status": status}
```

---

## Task 5: User Library Endpoint

```python
@app.get("/api/users/me/videos")
async def my_videos(user_id: str = Depends(require_auth)):
    """Returns list of videos this user has added/watched."""
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            SELECT v.video_id, v.title, v.duration_seconds, v.status,
                   uv.last_watched_at, uv.last_position_seconds
            FROM user_videos uv
            JOIN videos v ON uv.video_id = v.video_id
            WHERE uv.user_id = %s AND uv.deleted_at IS NULL
            ORDER BY uv.last_watched_at DESC NULLS LAST
        """, (user_id,))
        rows = cur.fetchall()
    conn.close()
    return [
        {"video_id": r[0], "title": r[1], "duration": r[2], "status": r[3],
         "last_watched_at": str(r[4]) if r[4] else None, "last_position": r[5]}
        for r in rows
    ]
```

---

## Task 6: Rate Limiting

```bash
pip install slowapi
```

Add to `backend/app.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Decorate the endpoints:
```python
@app.post("/api/ask", response_model=AskResponse)
@limiter.limit("30/minute")
async def ask_question(request: Request, body: AskRequest, ...):

@app.post("/api/process-video")
@limiter.limit("5/minute")
async def process_video(request: Request, body: ProcessRequest, ...):
```

**Note:** When using `@limiter.limit`, the first parameter must be `request: Request` (from FastAPI/Starlette). The Pydantic body model becomes the second parameter. Adjust the function signatures accordingly.

Add `slowapi` to `requirements.txt`.

---

## Task 7: Update `/api/ask` Auto-ingest for Background Worker

In `ask_question`, the current auto-ingest calls `await process_video(...)` synchronously. Change to check status:

```python
    # 2. Auto-ingest if not indexed
    if not index.is_indexed(video_id):
        status = _get_video_status(video_id)
        if status == "processing":
            raise HTTPException(status_code=202, detail="Video is still being processed. Try again shortly.")
        elif status == "failed":
            raise HTTPException(status_code=422, detail="Video processing failed. Try resubmitting.")
        else:
            # Not known — register and queue
            _register_video(video_id)
            # Can't use background_tasks here easily, so import and call directly
            import threading
            t = threading.Thread(target=_ingest_video_bg, args=(video_id, request.youtube_url, user_id or ""))
            t.start()
            raise HTTPException(status_code=202, detail="Video is being processed. Try again in a minute.")
```

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `backend/auth.py` | JWT verification middleware (new) |
| 2 | `backend/app.py` | Auth on endpoints, background worker, rate limiting, 3 new endpoints |
| 3 | `requirements.txt` | Add `PyJWT`, `slowapi` |

New endpoints after this session:
- `GET /api/health` — public
- `POST /api/process-video` — requires auth, returns immediately, ingests in background
- `POST /api/ask` — optional auth (demo video allowed without), rate limited
- `GET /api/videos/{video_id}/status` — public (polling)
- `GET /api/users/me/videos` — requires auth

---

## Self-Critical Audit Plan

### Audit 1: auth.py imports clean
```bash
source .venv/bin/activate
python3 -c "from backend.auth import require_auth, optional_auth; print('PASS')"
```
**PASS:** No import errors.

### Audit 2: Backend starts
```bash
uvicorn backend.app:app --port 8000 &
sleep 5
curl -s http://localhost:8000/api/health | python3 -m json.tool
kill %1 2>/dev/null
```
**PASS:** Returns `{"status": "ok", ...}`.

### Audit 3: Unauthenticated request to non-demo video → 401
```bash
uvicorn backend.app:app --port 8000 &
sleep 5
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=VRcixOuG-TU","question":"test","timestamp":0}')
echo "Status: $STATUS"
kill %1 2>/dev/null
```
**PASS:** Returns `401`.

### Audit 4: Demo video works without auth
```bash
uvicorn backend.app:app --port 8000 &
sleep 5
curl -s -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=3OmfTIf-SOU","question":"What is testing?","timestamp":60,"skip_quality_eval":true}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'answer' in d else f'FAIL: {d}')"
kill %1 2>/dev/null
```
**PASS:** Returns an answer (no auth required for demo video).

### Audit 5: Health stays public
```bash
curl -s http://localhost:8000/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('PASS' if d['status']=='ok' else 'FAIL')"
```
**PASS:** Returns OK without any auth header.

### Audit 6: Status polling endpoint works
```bash
curl -s http://localhost:8000/api/videos/3OmfTIf-SOU/status | python3 -m json.tool
```
**PASS:** Returns `{"video_id": "3OmfTIf-SOU", "status": "ready"}`.

### Audit 7: Unknown video returns 404
```bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/videos/XXXXXXXXXXX/status)
echo "Status: $STATUS"
```
**PASS:** Returns `404`.

### Audit 8: process-video requires auth
```bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/process-video \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=3OmfTIf-SOU"}')
echo "Status: $STATUS"
```
**PASS:** Returns `401` or `403` (not `200` or `500`).

### Audit 9: Rate limiting header present
```bash
curl -sI -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=3OmfTIf-SOU","question":"test","timestamp":0,"skip_quality_eval":true}' \
  | grep -i "x-ratelimit\|retry-after" | head -5
```
**PASS:** Shows rate limit headers (or at minimum, no crash).

### Audit 10: Tests pass
```bash
kill %1 2>/dev/null
pytest -q 2>&1 | tail -10
```
**PASS:** No regressions. (Document any pre-existing failures.)

---

## Worker Log

### Files changed
- `backend/auth.py` — created (JWT verify + `require_auth` / `optional_auth`)
- `backend/app.py` — added Limiter + RateLimitExceeded handler; added `_get_db_url`, `_register_video`, `_get_video_status`, `_update_video_status`, `_link_user_video`; refactored `process_video` to require auth + queue `_ingest_video_bg` via `BackgroundTasks` (rate-limited 5/min); refactored `ask_question` to optional auth + demo-only gate + status-aware 202 auto-ingest in a thread (rate-limited 30/min); added `GET /api/videos/{video_id}/status` and `GET /api/users/me/videos`.
- `requirements.txt` — added `PyJWT`, `slowapi`.

### Audit results
| # | Audit | Result |
|---|---|---|
| 1 | `auth.py` imports clean | PASS |
| 2 | Backend starts, `/api/health` returns ok | PASS — `{"status":"ok",...}` |
| 3 | Unauthenticated non-demo `/api/ask` → 401 | PASS — Status: 401 |
| 4 | Demo video works without auth | PASS — answer length 1422 chars (Groq key expired → Gemini fallback succeeded) |
| 5 | `/api/health` public | PASS |
| 6 | `/api/videos/3OmfTIf-SOU/status` | PASS — `{"video_id":"3OmfTIf-SOU","status":"ready"}` |
| 7 | Unknown video status → 404 | PASS — Status: 404 |
| 8 | `/api/process-video` no auth → 401 | PASS — Status: 401 |
| 9 | Rate-limit headers / no crash | PASS — server did not crash; `slowapi` does not emit `X-RateLimit-*` headers by default (would require `enabled` flag/config), but the limiter is registered (`app.state.limiter`) and the limit decorators are active. |
| 10 | `pytest` regressions | PRE-EXISTING failure: `tests/test_ingest.py` and 2 others fail to import with `ModuleNotFoundError: No module named 'pipeline'` (no `conftest.py` adds repo root to `sys.path`). Not introduced by this session. |

### Notes for next session
- `slowapi` requires `request: Request` as the **first** parameter — done. Pydantic body is now the second positional (`body: AskRequest`, `body: ProcessRequest`); frontend behaviour is unchanged.
- `process_video` no longer returns `ProcessResponse` (shape changed to `{video_id, status, message}`). The unused `ProcessResponse` import and model can be removed in a follow-up if desired.
- `ask_question` now returns `HTTP 202` with `detail` while a video is being ingested — frontend should poll `/api/videos/{id}/status` until `status == "ready"`.
- `Groq` API key in `.env` is expired (`401 invalid_request_error`); answers fall back to Gemini. Rotate `GROQ_API_KEY` when convenient.
