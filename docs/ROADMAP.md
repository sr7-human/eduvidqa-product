# EduVidQA — Product Roadmap & Gap Checklist

> Living document. Tracks the path from current MVP-on-localhost to the
> envisioned multi-tenant product (Vercel + Supabase + HF/Fly worker).
> Companion architecture diagram: [`ARCHITECTURE.mmd`](ARCHITECTURE.mmd).

**Legend:** 🟥 blocker · 🟧 needed for MVP launch · 🟨 needed for scale · 🟩 polish

---

## Vision

Multi-tenant web product where anyone signs up → adds a YouTube lecture →
gets a traceable AI tutor + interactive quizzes (auto checkpoints + on-demand)
+ spaced review. Every video is processed **exactly once globally** and reused
across all users. Deployable at $0/month for MVP.

---

## Phase 1 — Foundation (unblocks everything else)

### A. Security & secrets
- [ ] 🟥 Rotate `HF_TOKEN`, `GROQ_API_KEY`, `GEMINI_API_KEY` in `.env`
- [ ] 🟥 Lock CORS — replace `allow_origins=["*"]` in `backend/app.py` with explicit origin list
- [ ] 🟥 Add auth to `/api/ask` and `/api/process-video` (Supabase JWT verify)
- [ ] 🟥 Stop leaking server errors (`HTTPException(500, detail=str(exc))`)
- [ ] 🟧 Per-user + per-IP rate limiting (slowapi)
- [ ] 🟧 Pydantic input caps: `question` ≤ 2 KB, `timestamp` ≤ 6 h, validate `youtube_url`
- [ ] 🟧 Fix BYOK copy in `frontend/src/components/SettingsModal.tsx`

### B. Identity (Supabase Auth)
- [ ] 🟥 Provision Supabase project (free tier)
- [ ] 🟥 Enable Google OAuth + email magic link
- [ ] 🟥 `auth.users.id` becomes partition key for every user-owned row
- [ ] 🟧 Account / settings page (`/settings`)
- [ ] 🟨 Admin role for content moderation
- [ ] 🟩 Org / team accounts

### C. Database (Supabase Postgres + pgvector)
- [ ] 🟥 Enable extensions: `pgvector`, `pgmq`
- [ ] 🟥 Create core tables: `videos`, `video_chunks`, `user_videos`
- [ ] 🟥 Create quiz tables: `checkpoints`, `questions`, `quiz_attempts`, `review_queue`
- [ ] 🟥 RLS policies: global tables read-only for auth users; user tables owner-only
- [ ] 🟥 Migration script: re-embed existing 7 videos in `data/processed/` into pgvector
- [ ] 🟧 ULIDs / UUIDv7 for primary keys
- [ ] 🟧 Soft deletes (`deleted_at`) on user tables
- [ ] 🟨 Outbox / event-log table for analytics derivation
- [ ] 🟨 Versioned migrations (Supabase migrations or Alembic)

### D. Storage (Supabase Storage)
- [ ] 🟥 Create bucket `videos/` (private)
- [ ] 🟥 Refactor `pipeline/keyframes.py` to upload keyframes to Storage
- [ ] 🟧 Signed URLs for keyframe access
- [ ] 🟧 Confirm `.mp4` is deleted post-ingest (worker)
- [ ] 🟨 Optional cached `.mp4` bucket for zero-latency `live_frame`

### E. Pipeline cleanup & pgvector swap
- [ ] 🟥 Delete v1 modules: `pipeline/{rag,embeddings,evaluate,inference,inference_gemini,inference_gemini_video,inference_groq}.py`
- [ ] 🟥 Rename v2 → canonical (`rag_v2.py` → `rag.py`, etc.); update imports in `backend/app.py`
- [ ] 🟥 Fix `_last_error` bug in `pipeline/answer.py` (init at top)
- [ ] 🟥 Replace Chroma calls in `rag.py` with pgvector SELECT/INSERT
- [ ] 🟧 Pin `requirements.txt` versions
- [ ] 🟧 Constants: `PIPELINE_VERSION`, `EMBED_MODEL_VERSION`, `PROMPT_VERSION`
- [ ] 🟧 Address Jina monkey-patch fragility (pin torch or fork model)

### F. Job queue & worker
- [ ] 🟥 Atomic dedup: `INSERT INTO videos … ON CONFLICT DO NOTHING` before any work
- [ ] 🟥 Background worker process (separate from API); start with `pgmq`
- [ ] 🟥 Job states: `pending → processing → ready | failed` with `status_detail`
- [ ] 🟧 Worker auto-retry with exponential backoff
- [ ] 🟨 Dead-letter queue + alerts on repeat failures

### H. API contract fixes
- [ ] 🟥 `generation_time_seconds` vs `generation_time` mismatch
- [ ] 🟥 `ProcessResponse` shape mismatch
- [ ] 🟥 `HealthResponse` missing `model_name` in frontend type
- [ ] 🟧 Generate TS types from OpenAPI (`openapi-typescript`)
- [ ] 🟧 Versioned API path `/api/v1/...`
- [ ] 🟧 Standard error envelope `{error: {code, message, request_id}}`

### K. Deploy targets picked & wired
- [ ] 🟥 Hosts: Vercel (frontend), Supabase (DB/Storage/Auth), HF Space or Fly (API + worker)
- [ ] 🟥 Fix `vercel.json` rewrite (`${VITE_API_URL}` doesn't expand at runtime)
- [ ] 🟥 Dockerfile non-root user
- [ ] 🟥 Env matrix per host

---

## Phase 2 — Productize

### I. Frontend pages & routing
- [ ] 🟥 Add `react-router-dom`
- [ ] 🟥 Routes: `/`, `/login`, `/library`, `/watch/:videoId`, `/review`, `/settings`
- [ ] 🟥 Landing `/` — hero, demo, "try without signup" (1 video, rate-limited), CTA
- [ ] 🟥 Login `/login` — Supabase Auth UI
- [ ] 🟥 Library `/library` — recent videos, continue watching, review queue widget, "+ Add video"
- [ ] 🟥 Watch `/watch/:id` — current player + chat, plus checkpoint markers, "Test me", quiz panel, pause toast
- [ ] 🟧 Review `/review` — due questions queue
- [ ] 🟧 Auth context + protected route guard
- [ ] 🟧 Page-specific loading / empty / error states
- [ ] 🟧 Toast system (sonner / react-hot-toast)
- [ ] 🟧 Realtime subscription to `videos.status` for ingest progress
- [ ] 🟨 Mobile responsive layout
- [ ] 🟨 Keyboard shortcuts (space, q, /)
- [ ] 🟩 Dark mode

### J. Frontend cleanup
- [ ] 🟧 Delete unused `components/VideoInput.tsx` and `hooks/useAskQuestion.ts`
- [ ] 🟧 Remove `@tanstack/react-query` if unused
- [ ] 🟧 Move `DEFAULT_VIDEO_URL` out of `App.tsx` to env

### L. Observability
- [ ] 🟧 Structured JSON logging with `request_id`
- [ ] 🟧 Sentry on frontend + backend
- [ ] 🟧 Metrics: cache-hit rate, LLM cost / req, p95 `/api/ask` latency, quiz acceptance
- [ ] 🟨 OpenTelemetry traces (worker → LLM provider)
- [ ] 🟨 Cost dashboard (Groq + Gemini token spend)
- [ ] 🟨 Uptime monitor (UptimeRobot)

### M. Testing
- [ ] 🟧 Re-point pytest suite at pgvector `rag.py`
- [ ] 🟧 API contract test against OpenAPI schema
- [ ] 🟧 Playwright e2e: signup → add video → ask → quiz → review
- [ ] 🟨 Load test: 100 concurrent `/api/ask`
- [ ] 🟨 Cost regression test: budget per ingest

### K2. CI/CD
- [ ] 🟧 GitHub Actions: tests → build → deploy frontend (Vercel) + image (HF/Fly)
- [ ] 🟧 Separate dev / staging / prod Supabase projects
- [ ] 🟨 DB migration runner in CI
- [ ] 🟨 Custom domain + SSL

---

## Phase 3 — Quiz feature

### G. Checkpoints, questions, attempts, review
- [x] 🟧 Checkpoint placement algorithm in ingest (chunk + topic-shift, ~1 / 5–8 min)
- [x] 🟧 Question generation prompt + parser (Groq Llama path)
- [x] 🟧 Pre-generate checkpoint quizzes during ingest job
- [x] 🟧 `GET /videos/:id/checkpoints` (no answers leaked)
- [x] 🟧 `POST /videos/:id/quiz {end_ts}` — cache key `(video_id, ts_bucket_30s, prompt_version)` **global**
- [x] 🟧 `POST /quizzes/:id/attempts` — score, persist, update review queue
- [x] 🟧 `GET /users/me/review` — due questions across all videos
- [x] 🟨 Spaced repetition (SM-2 lite)
- [ ] 🟨 Per-user rate limit on custom quiz generation (1/min)
- [ ] 🟩 Question quality flagging UI
- [x] 🟧 **Chapter-based quiz system** — pretest / mid-recall / end-recall with per-chapter structure
- [x] 🟧 `GET /videos/:id/chapters` — ordered chapter list (YouTube or synthesized)
- [x] 🟧 `GET /videos/:id/quiz-schedule` — timeline events for player
- [x] 🟧 `GET /videos/:id/chapter-quiz` — questions by chapter + quiz_type
- [x] 🟧 `GET/PUT /users/me/quiz-pref` — user quiz blocking preference
- [x] 🟧 `GET /api/video-preview` — yt-dlp metadata probe for pre-ingest preview
- [x] 🟧 Per-option explanations (distractor analysis) in quiz generation
- [x] 🟧 Chapter-aware quiz prompts: pretest (curiosity), mid-recall (specific), end-recall (synthesis)

### Watch-page UX (depends on G + I)
- [x] 🟧 Timeline overlay with checkpoint dots (unseen / available / passed / missed)
- [x] 🟧 Persistent "Test me" pill in player chrome
- [x] 🟧 Quiz side panel (non-modal)
- [x] 🟧 Pause-detector hook → soft toast near checkpoint
- [x] 🟧 Review tray on home page
- [x] 🟧 **ChapterQuizModal** — full-screen quiz modal with per-type theming (pretest/mid/end)
- [x] 🟧 **Watch.tsx wiring** — quiz schedule fetch, timestamp-crossing detection, auto-pause + modal
- [x] 🟧 **Settings quiz pref toggle** — 3-option radio (use default / always / never pause)
- [x] 🟧 **Add Video preview modal** — shows duration + sections + quiz mention before confirm

---

## Phase 4 — Polish & growth

### N. Legal / compliance
- [ ] 🟧 Privacy policy + terms of service pages
- [ ] 🟧 Cookie / consent banner (EU)
- [ ] 🟧 GDPR delete-my-data endpoint
- [ ] 🟧 YouTube ToS / fair-use review before monetizing
- [ ] 🟨 DMCA takedown handling

### O. Docs
- [ ] 🟧 Replace `HANDOFF.md` with `ARCHITECTURE.md`
- [ ] 🟧 README rewrite: real env vars, deployment steps, contributing guide
- [ ] 🟩 User-facing docs site

### Growth
- [ ] 🟨 Org / team accounts
- [ ] 🟨 Billing (Stripe) — paid tier removes BYOK requirement
- [ ] 🟩 Public video catalog / discovery

---

## MVP cut (fastest public beta)

Ship Phase 1 + stripped Phase 3 + landing/login/library/watch from Phase 2.
Defer: org accounts, full SRS (just store missed Qs), realtime (poll 2s),
`pgmq` (use FastAPI `BackgroundTasks`), checkpoint pre-gen (gen on first viewer).
