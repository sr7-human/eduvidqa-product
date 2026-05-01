# Session L — Observability + CI/CD + Deploy

## Status: � COMPLETE (deploy deferred)
## Dependencies: J ✅ (Dockerfile fixed), K2 ✅ (frontend routing complete)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

Add structured JSON logging, Sentry error monitoring, a GitHub Actions CI pipeline, API contract tests, and deploy frontend to Vercel + backend to HF Space.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`

---

## Current State

- **Dockerfile** (24 lines) — already non-root (`USER app`), has healthcheck. Ready to push.
- **`.dockerignore`** (11 lines) — exists, excludes `.env`, `.venv/`, `data/`, etc.
- **`vercel.json`** — clean (no broken rewrite, just build config).
- **`.github/workflows/`** — has `deploy-tracker.yml` only (unrelated). No CI yet.
- **Backend** — 776 lines, 13 endpoints, auth + rate limiting working.
- **Frontend** — builds clean, all pages working.

---

## Task 1: Structured JSON Logging

**Create file:** `backend/logging_config.py`

```python
"""Structured JSON logging with request_id tracking."""
import logging, json, sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(""),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)

def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
```

**Add to `backend/app.py`** (near top, after existing imports):
```python
import uuid as _uuid
from backend.logging_config import setup_logging, request_id_var
setup_logging()

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(_uuid.uuid4())
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response
```

Note: `backend/app.py` already imports `uuid` — use `_uuid` alias or just reuse the existing import.

---

## Task 2: Sentry Integration

**Backend:**
```bash
pip install sentry-sdk[fastapi]
```

Add to `backend/app.py` (after `setup_logging()`):
```python
import sentry_sdk
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=0.1)
```

**Frontend:**
```bash
cd frontend && npm install @sentry/react
```

Add to `src/main.tsx` (before `ReactDOM.createRoot`):
```typescript
import * as Sentry from '@sentry/react';
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({ dsn: import.meta.env.VITE_SENTRY_DSN, tracesSampleRate: 0.1 });
}
```

Add `sentry-sdk[fastapi]` to `requirements.txt`.  
Add to `.env`: `SENTRY_DSN=` (empty for now).

---

## Task 3: API Contract Tests

**Create file:** `tests/test_api_contract.py`

```python
"""Verify API response shapes match expected contracts."""
import httpx
import pytest

BASE = "http://localhost:8000"

def test_health_shape():
    r = httpx.get(f"{BASE}/api/health")
    assert r.status_code == 200
    d = r.json()
    assert "status" in d and "model_name" in d

def test_ask_requires_auth_for_non_demo():
    r = httpx.post(f"{BASE}/api/ask", json={
        "youtube_url": "https://www.youtube.com/watch?v=VRcixOuG-TU",
        "question": "test", "timestamp": 0
    })
    assert r.status_code == 401

def test_ask_demo_no_auth():
    r = httpx.post(f"{BASE}/api/ask", json={
        "youtube_url": "https://www.youtube.com/watch?v=3OmfTIf-SOU",
        "question": "What is unit testing?", "timestamp": 60,
        "skip_quality_eval": True
    })
    # 200 if indexed, 202 if processing — both acceptable
    assert r.status_code in (200, 202)

def test_video_status():
    r = httpx.get(f"{BASE}/api/videos/3OmfTIf-SOU/status")
    assert r.status_code == 200
    assert r.json()["status"] in ("ready", "processing", "pending")

def test_unknown_video_404():
    r = httpx.get(f"{BASE}/api/videos/XXXXXXXXXXX/status")
    assert r.status_code == 404
```

---

## Task 4: GitHub Actions CI

**Create file:** `.github/workflows/ci.yml`

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest -q --ignore=tests/test_api_contract.py --ignore=tests/e2e_mac_m2.py
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci && npm run build
        env:
          VITE_API_URL: https://placeholder.hf.space
          VITE_SUPABASE_URL: https://placeholder.supabase.co
          VITE_SUPABASE_ANON_KEY: placeholder

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t eduvidqa .
      - run: docker run --rm eduvidqa whoami | grep -q app
```

---

## Task 5: Deploy Frontend to Vercel

1. Connect GitHub repo to Vercel (or use `vercel` CLI)
2. Settings:
   - Root directory: `frontend`
   - Framework: Vite
   - Build: `npm run build`
   - Output: `dist`
3. Environment variables:
   - `VITE_API_URL` = HF Space URL (or placeholder for now)
   - `VITE_SUPABASE_URL` = from `.env`
   - `VITE_SUPABASE_ANON_KEY` = from `.env`
4. Deploy → get preview URL
5. Document the URL in the Worker Log

---

## Task 6: Deploy Backend to HF Space

1. Create HF Space (Docker, CPU basic free)
2. Set secrets: `GROQ_API_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `CORS_ORIGINS`
3. Set `CORS_ORIGINS` to Vercel domain
4. Push code → auto-builds from Dockerfile
5. Test: `curl https://your-space.hf.space/api/health`
6. Document the URL in the Worker Log

**If deploy is not possible right now** (no HF/Vercel accounts), skip Tasks 5-6 and document "deploy deferred" in Worker Log. The CI + logging + Sentry work is still valuable.

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `backend/logging_config.py` | JSON logging + request_id (new) |
| 2 | `backend/app.py` | Logging setup + request_id middleware + Sentry init |
| 3 | `frontend/src/main.tsx` | Sentry init |
| 4 | `tests/test_api_contract.py` | 5 contract tests (new) |
| 5 | `.github/workflows/ci.yml` | CI pipeline (new) |
| 6 | `requirements.txt` | Add `sentry-sdk[fastapi]` |
| 7 | Vercel deploy | Frontend live (or deferred) |
| 8 | HF Space deploy | Backend live (or deferred) |

---

## Self-Critical Audit Plan

### Audit 1: Backend starts with JSON logging
```bash
source .venv/bin/activate
uvicorn backend.app:app --port 8000 &
sleep 5
curl -s http://localhost:8000/api/health > /dev/null
kill %1 2>/dev/null
```
**PASS:** Server stdout shows JSON log lines (not plain text).

### Audit 2: Request-ID in response headers
```bash
uvicorn backend.app:app --port 8000 &
sleep 5
curl -sI http://localhost:8000/api/health | grep -i "x-request-id"
kill %1 2>/dev/null
```
**PASS:** Header `X-Request-ID: <uuid>` present.

### Audit 3: Sentry doesn't crash without DSN
```bash
SENTRY_DSN="" python3 -c "from backend.app import app; print('OK')"
```
**PASS:** Prints OK — gracefully skips when DSN empty.

### Audit 4: Contract tests exist
```bash
ls tests/test_api_contract.py && grep -c "def test_" tests/test_api_contract.py
```
**PASS:** File exists, ≥ 4 test functions.

### Audit 5: CI workflow valid YAML
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```
**PASS:** Prints "valid".

### Audit 6: Frontend builds with Sentry
```bash
cd frontend && npm run build 2>&1 | tail -3
```
**PASS:** Build succeeds.

### Audit 7: Docker builds
```bash
docker build -t eduvidqa . 2>&1 | tail -3
docker run --rm eduvidqa whoami
```
**PASS:** Build succeeds, `whoami` returns `app`.

### Audit 8: logging_config.py imports
```bash
python3 -c "from backend.logging_config import setup_logging, request_id_var; print('OK')"
```
**PASS:** No errors.

---

## Worker Log

**Date:** 2026-04-30  
**Outcome:** All 8 audits PASS. Code tasks 1–4, 6 complete. Tasks 5–6 (Vercel + HF deploy) deferred — no accounts wired up yet.

### Files created/modified
- `backend/logging_config.py` (new) — JSON formatter + `request_id_var` ContextVar
- `backend/app.py` — added `setup_logging()`, request_id middleware, Sentry init (graceful when DSN empty)
- `frontend/src/main.tsx` — Sentry init guarded by `VITE_SENTRY_DSN`
- `tests/test_api_contract.py` (new) — 5 contract tests
- `.github/workflows/ci.yml` (new) — backend/frontend/docker jobs
- `requirements.txt` — added `sentry-sdk[fastapi]`
- `frontend/package.json` — added `@sentry/react`

### Audit results

**Audit 1: JSON logs** ✅
```
{"ts": "2026-04-30 22:10:21,582", "level": "INFO", "logger": "backend.app", "msg": "EduVidQA API starting up …", "request_id": ""}
```

**Audit 2: X-Request-ID header** ✅
```
x-request-id: b4d11d10-1784-4b1a-af41-87582275e1a9
```

**Audit 3: Sentry no-DSN** ✅
```
=== Audit 3: Sentry no-DSN ===
OK
```

**Audit 4: Contract tests** ✅ — file exists, 5 test functions. All pass against live server:
```
tests/test_api_contract.py::test_health_shape PASSED                     [ 20%]
tests/test_api_contract.py::test_ask_requires_auth_for_non_demo PASSED   [ 40%]
tests/test_api_contract.py::test_ask_demo_no_auth PASSED                 [ 60%]
tests/test_api_contract.py::test_video_status PASSED                     [ 80%]
tests/test_api_contract.py::test_unknown_video_404 PASSED                [100%]
============================== 5 passed in 37.17s ==============================
```

**Audit 5: CI YAML valid** ✅ — `valid`

**Audit 6: Frontend builds with Sentry** ✅
```
dist/index.html                   0.66 kB │ gzip:   0.45 kB
dist/assets/index-Chag9dPr.css   50.51 kB │ gzip:   7.61 kB
dist/assets/index-qYuMosgg.js   755.78 kB │ gzip: 229.90 kB
✓ built in 1.73s
```
(Bundle warning >500KB — non-blocking; future code-split task.)

**Audit 7: Docker build + non-root** ✅ — image built, `docker run --rm eduvidqa-test whoami` returned `app`.

**Audit 8: logging_config import** ✅ — `OK`

### Notes / fixups during execution
- Initial `app.py` patch had a missing closing `)` in `logger.warning(...)` — fixed before audits.
- Sentry import + init wrapped in try/except so missing/invalid DSN never crashes startup.
- Used existing `uuid` import in app.py (no `_uuid` alias needed).
- `npm install @sentry/react` reported 3 moderate vulns transitively — not in our direct deps, deferred.

### Deferred to future session
- Task 5: Vercel deploy (frontend) — needs Vercel account linkage.
- Task 6: HF Space deploy (backend) — needs HF account + secrets configured.
- CI workflow will run on next push to `main` — required GitHub secrets (`DATABASE_URL`, `GROQ_API_KEY`, `GEMINI_API_KEY`) need to be added in repo settings before first run, otherwise backend job will fail on env-dependent tests.
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->
