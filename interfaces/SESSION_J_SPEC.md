# Session J — API Contract Fixes + Deploy Prep

## Status: � COMPLETE
## One task file. All context is here — do NOT read HANDOFF.md, ROADMAP.md, or other SESSION_* files.

---

## What You're Doing

Fix 3 backend↔frontend field-name mismatches that silently break UI features, fix the broken Vercel rewrite, make the Dockerfile production-ready (non-root user), clean up unused frontend code, and move the hardcoded default video URL to env.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Frontend:** `cd frontend && npm run dev`  
**Backend:** `source .venv/bin/activate && uvicorn backend.app:app --reload --port 8000`

---

## Mismatch Summary

| Field | Backend (`backend/models.py`) | Frontend (`frontend/src/types/index.ts`) | Effect |
|---|---|---|---|
| `generation_time_seconds` | ✅ `AskResponse.generation_time_seconds` | ❌ reads `generation_time` | UI shows "Time: —" forever |
| `model_name` in health | ✅ `HealthResponse.model_name` | ❌ type omits `model_name` | Invisible but TS type wrong |
| `ProcessResponse.status` | ✅ Backend returns `message` string | ❌ Frontend expects `status: 'processed' \| 'already_cached'` | Type mismatch |

---

## Task 1: Fix `generation_time` → `generation_time_seconds`

### File: `frontend/src/types/index.ts` (93 lines)

**Line 21 — current:**
```typescript
  generation_time: number;
```
**Change to:**
```typescript
  generation_time_seconds: number;
```

**Line 59 — current (ChatMessage interface):**
```typescript
  generation_time?: number;
```
**Change to:**
```typescript
  generation_time_seconds?: number;
```

### File: `frontend/src/api/client.ts` (104 lines)

**Line 42 — mock response:**
```typescript
  generation_time: 2.3,
```
**Change to:**
```typescript
  generation_time_seconds: 2.3,
```

### File: `frontend/src/App.tsx` (196 lines)

**Line 106 — current:**
```typescript
        generation_time: res.generation_time,
```
**Change to:**
```typescript
        generation_time_seconds: res.generation_time_seconds,
```

**Also search for any other `generation_time` references in `frontend/src/`:**
```bash
grep -rn "generation_time" frontend/src/
```
Change ALL occurrences to `generation_time_seconds`. There may be display logic in components too.

---

## Task 2: Fix `HealthResponse` — add `model_name`

### File: `frontend/src/types/index.ts`

**Current (lines 36-40):**
```typescript
export interface HealthResponse {
  status: 'ok' | 'loading' | 'error';
  model_loaded: boolean;
  gpu_available: boolean;
}
```

**Change to:**
```typescript
export interface HealthResponse {
  status: 'ok' | 'loading' | 'error';
  model_loaded: boolean;
  model_name: string;
  gpu_available: boolean;
}
```

### File: `frontend/src/api/client.ts`

**Mock health response (line ~83):**
```typescript
  if (USE_MOCK) return { status: 'ok', model_loaded: true, gpu_available: false };
```
**Change to:**
```typescript
  if (USE_MOCK) return { status: 'ok', model_loaded: true, model_name: 'mock', gpu_available: false };
```

---

## Task 3: Fix `ProcessResponse` type

### File: `frontend/src/types/index.ts`

**Current (lines 43-49):**
```typescript
export interface ProcessResponse {
  video_id: string;
  title: string;
  duration: number;
  segment_count: number;
  status: 'processed' | 'already_cached';
}
```

**Change to (match what backend actually returns):**
```typescript
export interface ProcessResponse {
  video_id: string;
  title: string;
  duration: number;
  segment_count: number;
  message: string;
}
```

---

## Task 4: Fix Vercel rewrite

### File: `vercel.json` (11 lines)

**Current (broken — `${VITE_API_URL}` doesn't expand at runtime in Vercel):**
```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": "vite",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "${VITE_API_URL}/api/:path*"
    }
  ]
}
```

**Replace with (remove broken rewrite — frontend already uses build-time VITE_API_URL):**
```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": "vite"
}
```

---

## Task 5: Fix Dockerfile (non-root + healthcheck)

### File: `Dockerfile` (18 lines)

**Replace entire file with:**
```dockerfile
FROM python:3.10-slim

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R app:app /app

USER app

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health')"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

### Create `.dockerignore`:
```
.env
.venv/
data/
media/
notebooks/
scripts/
.git/
__pycache__/
*.pyc
node_modules/
frontend/node_modules/
```

---

## Task 6: Delete unused frontend code

### Delete `frontend/src/components/VideoInput.tsx`
```bash
rm frontend/src/components/VideoInput.tsx
```
Verify it's not imported anywhere:
```bash
grep -rn "VideoInput" frontend/src/ --include="*.tsx" --include="*.ts"
```
If it's imported somewhere, remove that import too.

### Delete `frontend/src/hooks/useAskQuestion.ts`
```bash
rm frontend/src/hooks/useAskQuestion.ts
```
It uses `@tanstack/react-query` `useMutation`. Check if anything else uses react-query:
```bash
grep -rn "react-query\|useQuery\|useMutation\|QueryClient" frontend/src/ --include="*.tsx" --include="*.ts"
```

**After deleting `useAskQuestion.ts`**, only `main.tsx` still uses react-query (for `QueryClientProvider`). Since nothing uses `useQuery` or `useMutation` anymore:

1. Remove react-query from `main.tsx` — simplify to:
```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

2. Uninstall the package:
```bash
cd frontend && npm uninstall @tanstack/react-query
```

---

## Task 7: Move DEFAULT_VIDEO_URL to env

### File: `frontend/src/App.tsx`

**Current (line 9):**
```typescript
const DEFAULT_VIDEO_URL = 'https://www.youtube.com/watch?v=3OmfTIf-SOU';
```

**Change to:**
```typescript
const DEFAULT_VIDEO_URL = import.meta.env.VITE_DEFAULT_VIDEO_URL || 'https://www.youtube.com/watch?v=3OmfTIf-SOU';
```

### File: `frontend/.env` — add:
```
VITE_DEFAULT_VIDEO_URL=https://www.youtube.com/watch?v=3OmfTIf-SOU
```

---

## Deliverables

| # | File | Change |
|---|---|---|
| 1 | `frontend/src/types/index.ts` | Fix `generation_time` → `generation_time_seconds`, add `model_name` to Health, fix ProcessResponse |
| 2 | `frontend/src/api/client.ts` | Fix mock response fields |
| 3 | `frontend/src/App.tsx` | Fix `generation_time` reference, move DEFAULT_VIDEO_URL to env |
| 4 | `frontend/src/main.tsx` | Remove react-query wrapper |
| 5 | `vercel.json` | Remove broken rewrite |
| 6 | `Dockerfile` | Non-root user + healthcheck |
| 7 | `.dockerignore` | New file |
| 8 | `frontend/.env` | Add VITE_DEFAULT_VIDEO_URL |
| 9 | Deleted: `VideoInput.tsx`, `useAskQuestion.ts` | Unused code removed |
| 10 | Uninstalled: `@tanstack/react-query` | Unused dependency removed |

---

## Self-Critical Audit Plan

Run these checks IN ORDER. Every check must pass.

### Audit 1: No bare `generation_time` left (must be `generation_time_seconds` everywhere)
```bash
grep -rn "generation_time" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "generation_time_seconds"
```
**PASS:** Returns EMPTY. Every occurrence says `generation_time_seconds`.

### Audit 2: Frontend builds with zero errors
```bash
cd frontend && npm run build 2>&1 | tail -20
```
**PASS:** Build succeeds. Zero TypeScript errors. No "Cannot find" or "Property does not exist" messages.

### Audit 3: Mock response matches types
```bash
grep -A2 "generation_time_seconds" frontend/src/api/client.ts
grep "model_name.*mock" frontend/src/api/client.ts
```
**PASS:** Mock has `generation_time_seconds: 2.3` and `model_name: 'mock'`.

### Audit 4: ProcessResponse has `message` not `status`
```bash
grep -A6 "interface ProcessResponse" frontend/src/types/index.ts
```
**PASS:** Has `message: string`. Does NOT have `status: 'processed' | 'already_cached'`.

### Audit 5: HealthResponse has `model_name`
```bash
grep -A5 "interface HealthResponse" frontend/src/types/index.ts
```
**PASS:** Contains `model_name: string`.

### Audit 6: Vercel rewrite removed
```bash
cat vercel.json
```
**PASS:** No `rewrites` section. No `${VITE_API_URL}`.

### Audit 7: Dockerfile runs as non-root
```bash
docker build -t eduvidqa-test . 2>&1 | tail -5
docker run --rm eduvidqa-test whoami
```
**PASS:** Build succeeds. `whoami` returns `app`, NOT `root`.

### Audit 8: .dockerignore exists and excludes .env
```bash
head -3 .dockerignore
```
**PASS:** File exists, first lines include `.env` and `.venv/`.

### Audit 9: Unused files deleted
```bash
ls frontend/src/components/VideoInput.tsx 2>&1
ls frontend/src/hooks/useAskQuestion.ts 2>&1
```
**PASS:** Both say "No such file or directory".

### Audit 10: react-query removed
```bash
grep -rn "react-query\|QueryClient\|useMutation\|useQuery" frontend/src/ --include="*.ts" --include="*.tsx"
```
**PASS:** Returns EMPTY.

### Audit 11: DEFAULT_VIDEO_URL reads from env
```bash
grep "DEFAULT_VIDEO_URL" frontend/src/App.tsx
grep "VITE_DEFAULT_VIDEO_URL" frontend/.env
```
**PASS:** App.tsx uses `import.meta.env.VITE_DEFAULT_VIDEO_URL`. `.env` has the variable set.

### Audit 12: Backend still works (regression check)
```bash
cd /Users/shubhamkumar/eduvidqa-product
source .venv/bin/activate
uvicorn backend.app:app --port 8000 &
sleep 5
curl -s http://localhost:8000/api/health | python3 -m json.tool
kill %1 2>/dev/null
```
**PASS:** Returns 200 with `{"status": "ok", ...}`.

---

## Worker Log

### Audit 1 — No bare `generation_time`
```
$ grep -rn "generation_time" frontend/src/ --include="*.ts" --include="*.tsx" | grep -v "generation_time_seconds"
AUDIT 1 PASS: empty
```

### Audit 2 — Frontend builds
First run flagged a pre-existing TS6133 unused-var (`playerReady` from `useState`) that strict `tsc` rejected. Fixed by destructuring as `[, setPlayerReady]` (state setter is still used; reader was never read). Re-ran:
```
> tsc && vite build
vite v5.4.21 building for production...
✓ 646 modules transformed.
dist/index.html                   0.66 kB │ gzip:   0.45 kB
dist/assets/index-DWP_hS0f.css   45.77 kB │ gzip:   6.93 kB
dist/assets/index-7uP4RniT.js   430.36 kB │ gzip: 136.06 kB
✓ built in 1.20s
```

### Audit 3 — Mock response fields
```
  generation_time_seconds: 2.3,
  if (USE_MOCK) return { status: 'ok', model_loaded: true, model_name: 'mock', gpu_available: false };
```

### Audit 4 — ProcessResponse
```
export interface ProcessResponse {
  video_id: string;
  title: string;
  duration: number;
  segment_count: number;
  message: string;
}
```

### Audit 5 — HealthResponse
```
export interface HealthResponse {
  status: 'ok' | 'loading' | 'error';
  model_loaded: boolean;
  model_name: string;
  gpu_available: boolean;
}
```

### Audit 6 — vercel.json
```
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": "vite"
}
```

### Audit 7 — Dockerfile non-root
Installed Colima + Docker via Homebrew, started VM (`colima start --cpu 2 --memory 4 --disk 20`), ran full production build to completion.
```
$ docker build -t eduvidqa-test .
...
Step 11/12 : HEALTHCHECK ...
Step 12/12 : CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
Successfully built acc749f50617
Successfully tagged eduvidqa-test:latest
(image: 3.38 GB content / 9.66 GB on disk)

$ docker run --rm eduvidqa-test whoami
app
$ docker run --rm eduvidqa-test id
uid=999(app) gid=999(app) groups=999(app)
```
**PASS** — container runs as non-root `app` (uid 999). All 12 layers built, healthcheck + CMD applied cleanly. One tweak made during the audit: added `--default-timeout=300` to the `pip install` line so flaky networks don't kill the build at 60s.

### Audit 8 — .dockerignore
```
$ head -3 .dockerignore
.env
.venv/
data/
```

### Audit 9 — Deleted files
```
ls: frontend/src/components/VideoInput.tsx: No such file or directory
ls: frontend/src/hooks/useAskQuestion.ts: No such file or directory
```
(Empty `frontend/src/hooks/` directory was also removed.)

### Audit 10 — react-query removed
```
$ grep -rn "react-query|QueryClient|useMutation|useQuery" frontend/src/ --include="*.ts" --include="*.tsx"
EMPTY PASS
$ grep '"@tanstack/react-query"' frontend/package.json
REMOVED OK
```

### Audit 11 — DEFAULT_VIDEO_URL from env
```
const DEFAULT_VIDEO_URL = import.meta.env.VITE_DEFAULT_VIDEO_URL || 'https://www.youtube.com/watch?v=3OmfTIf-SOU';
VITE_DEFAULT_VIDEO_URL=https://www.youtube.com/watch?v=3OmfTIf-SOU
```

### Audit 12 — Backend regression
```
$ curl -s http://localhost:8000/api/health | python3 -m json.tool
{
    "status": "ok",
    "model_loaded": true,
    "model_name": "groq/llama-4-scout-17b",
    "gpu_available": false
}
```

### Notes
- Found and updated **two extra display sites** the spec didn't list explicitly: `frontend/src/components/AnswerDisplay.tsx` (line 33) and `frontend/src/components/ChatInterface.tsx` (lines 202–204) — both consumed `generation_time` and would have shown `undefined.toFixed()` runtime errors after the type rename. Now both use `generation_time_seconds`.
- Empty `frontend/src/hooks/` directory removed after deleting `useAskQuestion.ts`.
- Pre-existing unused `playerReady` reader in `App.tsx` was the only build blocker — fixed minimally without touching surrounding logic.
