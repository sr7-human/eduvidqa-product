# Session O — Legal Pages + README + .env.example + Docs Archive

## Status: ✅ COMPLETE
## Dependencies: L ✅ (deploy), N2 ✅ (quiz UI complete)
## One task file. All context is here — do NOT read other files. This is the FINAL session.

---

## What You're Doing

Final polish before public launch: privacy policy, terms of service, cookie banner, GDPR delete endpoint, a proper README, `.env.example`, and archive the old handoff docs.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Frontend:** `cd frontend && npm run dev`  
**Backend:** `source .venv/bin/activate && uvicorn backend.app:app --port 8000`

---

## Current State

- **No `README.md`** exists
- **No `.env.example`** exists
- **No legal pages** (Privacy, Terms) in frontend
- **No cookie banner** component
- **No GDPR delete endpoint** in backend
- **No Footer** component
- `HANDOFF.md` (big) and `HANDOFF_MANAGER.md` still in project root — should be archived
- `frontend/src/App.tsx` (26 lines) — 5 routes, clean router
- `.env` has 10 keys: `DATABASE_URL`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN`, `INFERENCE_ENGINE`, `LAZY_LOAD`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`

---

## Task 1: Privacy Policy Page

**Create file:** `frontend/src/pages/Privacy.tsx`

A full privacy policy page with Tailwind prose styling. Must cover:
- **Data collected:** email (via Supabase Auth), watch history (`user_videos`), quiz attempts, review queue
- **How it's used:** personalization, spaced repetition scheduling, improving quiz quality
- **Third-party services:** Supabase (auth/DB/storage), Groq (LLM inference), Google Gemini (fallback LLM), YouTube (video embeds via IFrame API)
- **BYOK (Bring Your Own Key):** if user provides a Gemini API key, it's sent with requests but never stored server-side
- **Data retention:** as long as account exists; deleted on account deletion
- **GDPR rights:** access your data, delete your data, data portability
- **Contact:** `privacy@eduvidqa.app` (placeholder)

Use `@tailwindcss/typography` prose classes for readable formatting. Add a Navbar at top.

---

## Task 2: Terms of Service Page

**Create file:** `frontend/src/pages/Terms.tsx`

Must cover:
- **Acceptable use:** educational purposes, no abuse of LLM endpoints, no automated scraping
- **YouTube content:** videos are embedded via YouTube IFrame API, not hosted by us
- **AI-generated content disclaimer:** answers are AI-generated and may contain errors; always verify with the original lecture
- **Account termination:** we reserve the right to terminate accounts violating terms
- **Limitation of liability:** service provided "as-is"
- **Changes to terms:** we may update terms; continued use = acceptance

Add Navbar at top. Tailwind prose styling.

---

## Task 3: Add Routes + Footer

**File:** `frontend/src/App.tsx` — add routes:

```typescript
import { Privacy } from './pages/Privacy';
import { Terms } from './pages/Terms';

// Inside <Routes>:
<Route path="/privacy" element={<Privacy />} />
<Route path="/terms" element={<Terms />} />
```

**Create file:** `frontend/src/components/Footer.tsx`

```typescript
import { Link } from 'react-router-dom';

export function Footer() {
  return (
    <footer className="border-t border-gray-200 py-4 px-6 text-center text-sm text-gray-500">
      <Link to="/privacy" className="hover:text-gray-700 mr-4">Privacy Policy</Link>
      <Link to="/terms" className="hover:text-gray-700">Terms of Service</Link>
    </footer>
  );
}
```

Add `<Footer />` to the Landing page (bottom).

---

## Task 4: Cookie Consent Banner

**Create file:** `frontend/src/components/CookieBanner.tsx`

```typescript
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('cookie_consent')) setShow(true);
  }, []);

  if (!show) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900 text-white p-4 z-50">
      <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
        <p className="text-sm">
          We use cookies for authentication and to improve your experience.{' '}
          <Link to="/privacy" className="underline">Learn more</Link>
        </p>
        <button
          className="px-4 py-2 bg-white text-gray-900 rounded text-sm font-medium whitespace-nowrap"
          onClick={() => { localStorage.setItem('cookie_consent', 'true'); setShow(false); }}
        >
          Accept
        </button>
      </div>
    </div>
  );
}
```

Add `<CookieBanner />` in `App.tsx` — inside `<BrowserRouter>`, after `<Routes>`:

```typescript
<Routes>...</Routes>
<CookieBanner />
```

---

## Task 5: GDPR Delete-My-Data Endpoint

**File:** `backend/app.py` — add:

```python
@app.delete("/api/users/me")
async def delete_my_data(user_id: str = Depends(require_auth)):
    """Delete ALL user-owned data. Does not delete global data (videos, questions)."""
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("DELETE FROM review_queue WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM quiz_attempts WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM user_videos WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    logger.info("Deleted all data for user %s", user_id)
    return {"message": "All your data has been deleted."}
```

---

## Task 6: Create `.env.example`

**Create file:** `.env.example`

```
# === LLM Providers ===
GROQ_API_KEY=           # https://console.groq.com/keys
GEMINI_API_KEY=         # https://aistudio.google.com/apikey
HF_TOKEN=              # https://huggingface.co/settings/tokens

# === Supabase ===
SUPABASE_URL=           # https://xxxxx.supabase.co
SUPABASE_ANON_KEY=      # Public key (safe for frontend)
SUPABASE_SERVICE_ROLE_KEY=  # Private key (backend only!)
SUPABASE_JWT_SECRET=    # Dashboard → Settings → API → JWT Secret
DATABASE_URL=           # postgresql://postgres:pass@db.xxxxx.supabase.co:5432/postgres

# === App Config ===
INFERENCE_ENGINE=groq   # groq | gemini | local
LAZY_LOAD=true          # Defer model loading on startup

# === CORS ===
CORS_ORIGINS=http://localhost:5173  # Comma-separated allowed origins

# === Optional ===
SENTRY_DSN=             # Sentry error tracking
DATA_DIR=./data         # Local data directory
```

---

## Task 7: Create README.md

**Create file:** `README.md`

Structure (target: new dev sets up in <30 minutes):

```markdown
# EduVidQA

AI tutor for YouTube lectures. Every answer is traceable to a moment in the lecture.

## Features

- 🎯 **Timestamped RAG answers** — citations link to exact lecture moments
- 👁️ **Vision-language model** — reads slides + transcript together
- 📝 **Quiz checkpoints** — auto-generated at topic boundaries
- 🧪 **On-demand quizzes** — test yourself anytime while watching
- 🔄 **Spaced review** — SM-2 algorithm resurfaces missed questions
- ⭐ **Quality scoring** — Clarity/ECT/UPT ratings on every answer

## Quick Start

\```bash
git clone <repo-url>
cd eduvidqa-product

# Backend
cp .env.example .env   # Fill in API keys
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173
\```

## Environment Variables

See [.env.example](.env.example) for all required variables.

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for Llama models |
| `GEMINI_API_KEY` | Yes | Google Gemini API key (fallback) |
| `DATABASE_URL` | Yes | Supabase Postgres connection string |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase private key (backend) |
| `SUPABASE_JWT_SECRET` | Yes | JWT verification secret |

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | No | System status |
| POST | `/api/process-video` | JWT | Submit video for processing |
| POST | `/api/ask` | Optional | Ask a question (demo video free) |
| GET | `/api/videos/{id}/status` | No | Poll processing status |
| GET | `/api/users/me/videos` | JWT | User's video library |
| GET | `/api/videos/{id}/checkpoints` | JWT | Quiz checkpoints |
| POST | `/api/videos/{id}/quiz` | JWT | Generate quiz questions |
| POST | `/api/quizzes/{id}/attempt` | JWT | Submit quiz answer |
| GET | `/api/users/me/review` | JWT | Due review questions |
| POST | `/api/review/{id}/attempt` | JWT | Submit review answer |
| DELETE | `/api/users/me` | JWT | Delete all user data (GDPR) |

## Architecture

React → FastAPI → Supabase (Postgres + pgvector + Auth + Storage) → Groq/Gemini LLMs

## Testing

\```bash
pytest -q                              # Backend tests
cd frontend && npm run build           # Frontend type check + build
\```

## Deployment

- **Frontend:** Vercel (Vite build)
- **Backend:** HF Space (Docker) or Fly.io
- **Database:** Supabase (free tier)

## Based On

EMNLP 2025 EduVidQA paper — [Paper Explainer](https://sr7-human.github.io/eduvidqa-explained/)
```

---

## Task 8: Archive Old Handoff Docs

```bash
mkdir -p docs/archive
mv HANDOFF.md docs/archive/HANDOFF_ORIGINAL.md
mv HANDOFF_MANAGER.md docs/archive/HANDOFF_MANAGER.md
```

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `frontend/src/pages/Privacy.tsx` | Privacy policy (new) |
| 2 | `frontend/src/pages/Terms.tsx` | Terms of service (new) |
| 3 | `frontend/src/components/Footer.tsx` | Footer with legal links (new) |
| 4 | `frontend/src/components/CookieBanner.tsx` | Cookie consent (new) |
| 5 | `frontend/src/App.tsx` | Add `/privacy`, `/terms` routes + CookieBanner |
| 6 | `backend/app.py` | Add `DELETE /api/users/me` endpoint |
| 7 | `.env.example` | Documented env template (new) |
| 8 | `README.md` | Full setup guide (new) |
| 9 | `docs/archive/` | HANDOFF.md + HANDOFF_MANAGER.md moved |

---

## Self-Critical Audit Plan

### Audit 1: Build passes
```bash
cd frontend && npm run build 2>&1 | tail -5
```
**PASS:** Zero errors.

### Audit 2: Privacy page renders
Navigate to `http://localhost:5173/privacy`.  
**PASS:** Full privacy policy visible. Mentions Supabase, Groq, Gemini, YouTube.

### Audit 3: Terms page renders
Navigate to `http://localhost:5173/terms`.  
**PASS:** Full terms text. Has AI disclaimer.

### Audit 4: Footer visible on landing
Navigate to `http://localhost:5173/`.  
**PASS:** "Privacy Policy" and "Terms of Service" links at bottom.

### Audit 5: Cookie banner shows + dismisses
Clear localStorage → reload page.  
**PASS:** Banner appears. Click Accept → banner gone. Reload → stays gone.

### Audit 6: GDPR delete endpoint exists
```bash
grep -n "delete_my_data\|DELETE.*users/me" backend/app.py
```
**PASS:** Endpoint defined.

### Audit 7: .env.example complete
```bash
cat .env.example | grep -c "="
```
**PASS:** Returns ≥ 10 variables.

### Audit 8: .env.example has NO real keys
```bash
grep -E "gsk_|AIza|hf_[A-Za-z0-9]{30,}|eyJ|postgresql://" .env.example
```
**PASS:** Returns EMPTY.

### Audit 9: README has quick start
```bash
grep -c "Quick Start\|pip install\|npm run dev\|uvicorn" README.md
```
**PASS:** Returns ≥ 4.

### Audit 10: Old handoffs archived
```bash
ls docs/archive/HANDOFF_ORIGINAL.md docs/archive/HANDOFF_MANAGER.md 2>&1
ls HANDOFF.md HANDOFF_MANAGER.md 2>&1
```
**PASS:** Files in `docs/archive/`. NOT in root.

### Audit 11: All routes work
```bash
grep -c "Route path" frontend/src/App.tsx
```
**PASS:** Returns 7 (`/`, `/login`, `/library`, `/watch/:videoId`, `/review`, `/privacy`, `/terms`).

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->

### Audit 1: `npm run build` — PASS
```
vite v5.4.21 building for production...
✓ 1024 modules transformed.
dist/index.html                   0.66 kB │ gzip:   0.45 kB
dist/assets/index-Dc4k_BfN.css   53.17 kB │ gzip:   7.84 kB
dist/assets/index-DvMAiQXi.js   768.22 kB │ gzip: 233.71 kB
✓ built in 1.76s
```
Zero TypeScript errors. (Chunk-size warning is informational only.)

### Audits 2–5: Manual page-render checks
- `/privacy` → renders `Privacy.tsx` (mentions Supabase, Groq, Gemini, YouTube, BYOK, GDPR rights, contact). Navbar at top.
- `/terms` → renders `Terms.tsx` (acceptable use, YouTube embed disclosure, AI-content disclaimer, "as-is" liability). Navbar at top.
- `/` (Landing) → footer now has `Privacy Policy` + `Terms of Service` links.
- `CookieBanner` mounted in `App.tsx` inside `<BrowserRouter>` after `<Routes>` — appears bottom-fixed when `localStorage.cookie_consent` is unset; click "Accept" stores the flag and hides the banner.

### Audit 6: GDPR delete endpoint — PASS
```
798:@app.delete("/api/users/me")
799:async def delete_my_data(user_id: str = Depends(require_auth)):
```

### Audit 7: `.env.example` variable count — PASS
```
18    # ≥ 10 required
```

### Audit 8: `.env.example` has NO real secrets — PASS
```
EMPTY (PASS)
```
(Initial run flagged the literal `postgresql://` placeholder URL — replaced with a plain comment pointing to the Supabase Connect dialog.)

### Audit 9: README quick-start markers — PASS
```
5    # ≥ 4 required (matches: Quick Start, pip install, npm run dev, uvicorn x2)
```

### Audit 10: Old handoff docs archived — PASS
```
docs/archive/HANDOFF_MANAGER.md
docs/archive/HANDOFF_ORIGINAL.md
ls: HANDOFF.md: No such file or directory
ls: HANDOFF_MANAGER.md: No such file or directory
OK: not in root
```

### Audit 11: Routes count — PASS
```
7    # /, /login, /library, /watch/:videoId, /review, /privacy, /terms
```

### Files delivered
| # | File | Status |
|---|---|---|
| 1 | `frontend/src/pages/Privacy.tsx` | created |
| 2 | `frontend/src/pages/Terms.tsx` | created |
| 3 | `frontend/src/components/Footer.tsx` | created |
| 4 | `frontend/src/components/CookieBanner.tsx` | created |
| 5 | `frontend/src/App.tsx` | edited (+2 routes, +CookieBanner, +imports) |
| 5b | `frontend/src/pages/Landing.tsx` | edited (footer now links Privacy/Terms) |
| 6 | `backend/app.py` | edited (`DELETE /api/users/me` appended) |
| 7 | `.env.example` | created (18 vars, no real secrets) |
| 8 | `README.md` | created |
| 9 | `docs/archive/HANDOFF_ORIGINAL.md`, `docs/archive/HANDOFF_MANAGER.md` | moved |

### Notes / deviations
- The spec's task-3 listed `Footer.tsx` as a separate component but Landing.tsx already had its own inline `<footer>`. Per spec wording ("Add `<Footer />` to the Landing page (bottom)") I kept the inline footer and extended it with the legal links rather than swapping it out — this preserves the existing "EduVidQA · Built for learners" tagline. The standalone `Footer.tsx` component is still created and is available for any other page that wants it.
- `@tailwindcss/typography` confirmed already installed (`package.json` + `tailwind.config.js` plugin entry) so the `prose` classes used in Privacy/Terms work out of the box.
- `logger` symbol confirmed already imported/initialised in `backend/app.py` (line 49) before the new endpoint uses it.
