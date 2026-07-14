# 📒 MUNIMJI — Project Evolution Ledger

> **Project:** eduvidqa-product (AI Teaching Assistant for YouTube lecture videos)
> **Location:** `/Users/shubhamkumar/eduvidqa-product`
> **Live:** Frontend → `eduvidqa-product.vercel.app` (Vercel) · Backend → HF Space `inquisitiveidiot/eduvidqa`

---

## ⚠️ MANDATORY UPDATE RULE

> **Every AI session working on `eduvidqa-product/` MUST append a session entry before ending work.**
> History is the value. This file is the single source of truth for project evolution.
>
> **Format:**
> ```
> ### Session N — [Short Title]
> **Date:** · **AI:** · **Context:**
> **What was done:** - [numbered]
> **Key Decisions:** - [rationale]
> **Files Modified:** - [paths]
> **Status:** ✅ COMPLETE / 🔄 IN PROGRESS / ⏸️ PAUSED
> **Next Steps:** - [what comes next]
> ```

---

## 🧭 Architecture Cheat-Sheet (read before touching anything)

- **Deploy is NOT git-auto.**
  - **Frontend → Vercel:** manual only — `cd frontend && vercel --prod --yes` (account `sr7-human`). `frontend/dist` is gitignored; Vercel builds from source.
  - **Backend → HF Space:** `origin/main` has a big `data/` dump that HF rejects (>10 MB). Deploy via **slim branch**: `git checkout -B hf-deploy hf/main && git checkout main -- <code files> && git commit && git push hf hf-deploy:main`.
- **Ingest pipeline (two-phase):** Phase 1 transcript → `transcript_ready` (watchable immediately, transcript-only answers + "not fully accurate yet" note). Phase 2 download → SSIM keyframes → digest → checkpoints → quizzes → `ready`.
- **Local ingest = the reliable workaround:** `python scripts/ingest_one_video.py <url>` runs from a **residential IP** (not blocked by YouTube) and writes to the **same production DB** → reflects globally. Link to a user via `user_videos` (see below).
- **DB (Supabase pgvector):** tables `videos`, `video_chunks`, `keyframe_embeddings`, `user_videos`, `checkpoints`. Statuses: `processing → transcript_ready → ready` | `failed`.

---

## 🚧 KNOWN BLOCKER — YouTube blocks the Space's datacenter IP

The single biggest reliability issue. Verified 2026-07-08/09:
- YouTube throttles/drops connections from the HF Space's **datacenter IP** — hits oEmbed, yt-dlp metadata, transcript API, and video download. It is **intermittent** (works in some windows, blocked in others).
- **Free fixes attempted and FAILED on the Space:**
  - Admin cookies (`YOUTUBE_COOKIES_B64` secret) → still `SSL UNEXPECTED_EOF` (blocked before cookies matter).
  - `curl_cffi` Chrome impersonation → `curl (35) invalid library` (curl_cffi's TLS backend doesn't work in the `python:3.10-slim` container). **Reverted.**
- **Conclusion:** the block is IP-level. The ONLY reliable fix is a **residential proxy** (~$1–6/mo, e.g. Webshare — the transcript lib ships `WebshareProxyConfig`; yt-dlp takes a `proxy` opt). Until then: **local ingest** for admin-curated content.

---

## 🗺️ PLANNED FEATURE — Playlist ingestion (resumable) + Playlists tab

**Idea (Shubham, 2026-07-09):** let users submit a whole **playlist**; ingest videos one-by-one; if an API/quota limit is hit, **resume the next day from the video it stopped at**; give playlists their own **tab / UI**.

**Current state:** backend `process_video` already detects a playlist URL (`_extract_playlist_id`) and bulk-queues every video. Missing: playlist as a first-class entity, resumable progress, and UI.

**Proposed design:**
1. **Data model:** new `playlists` (id, user_id, playlist_id, title, total_count, created_at) + `playlist_videos` (playlist_id, video_id, position, status). Per-video status drives resume.
2. **Resumable queue:** worker processes videos sequentially; on quota/limit error, mark that video `queued` (not `failed`), stop, and record a `resume_from` pointer. "Resume" re-starts at the first non-`ready` video. Skip already-`ready` ones.
3. **Quota awareness:** detect Gemini/Groq 429/quota errors distinctly from real failures so resume knows it was a limit, not a broken video.
4. **UI — new Playlists tab:** list playlists with a progress bar (e.g. "12 / 40 ready"), a **Resume** button, and per-video status chips. Likely a dedicated view separate from the single-video Library grid.

**⚠️ Dependency / caveat:** bulk playlist ingest **amplifies the YouTube-blocking problem** (40 videos = 40× the requests). This feature is only pleasant once the **residential proxy** is in place — OR if playlists are ingested via **local/admin** ingest. Flag this before building the user-facing version.

**Suggested phasing:** Phase 1 = backend (playlist model + resumable sequential queue + quota detection). Phase 2 = frontend (Playlists tab, progress, resume). Do proxy first (or gate playlists to admin/local) for reliability.

---

## 📜 Session Log

### Session 1 — YouTube reliability deep-dive + playlist planning
**Date:** 2026-07-08 → 2026-07-09
**AI:** GitHub Copilot (agent)
**Context:** User reported videos failing to ingest, a stuck "Checking…" button, a "site can't be reached" error, and asked whether the "watch-while-processing" feature still existed.

**What was done:**
1. Fixed the **"Checking…" hang**: `/api/video-preview` used yt-dlp (88 s → 502 from the Space IP). Switched to fast **oEmbed**; added an **8 s frontend timeout** that falls back to direct-add so the button can never hang.
2. Added **android/ios yt-dlp player_client** fallback for restricted videos (e.g. `SYDG5Dfueds` needed it).
3. Added a **Whisper fallback** (`openai-whisper`, gated by `WHISPER_MODEL`) for no-caption videos, wired into `chunk_transcript`.
4. Pre-wired **admin YouTube cookies** (`YOUTUBE_COOKIES_B64` secret → `get_cookiefile()` + `build_transcript_api()`), set the secret from the user's cookie file, restarted the Space.
5. Tested reliability fixes end-to-end against the live Space with a minted JWT → **cookies and curl_cffi both failed** (IP-level block). **Reverted** curl_cffi.
6. Confirmed the **"watch-while-processing" feature is fully intact** (transcript_ready → "watch now", transcript-only answers + accuracy warning, auto-upgrade on keyframes).
7. Diagnosed a **"site can't be reached"** issue as a **DNS/routing** problem (network couldn't reach Vercel's new IPs; `76.76.21.21` worked) — user fixed via DNS change.
8. Ingested **PCA** and **Neel Nanda "Mechanistic Interpretability"** videos **locally** (residential IP) into production.

**Key Decisions:**
- Preview is cosmetic → must never block the add flow (timeout + direct-add fallback).
- Free anti-blocking measures (cookies, TLS impersonation) don't beat an IP-level block → **residential proxy** is the real fix; **local ingest** is the free interim workaround.
- Playlist feature is worth building but **depends on the proxy** for a good user experience.

**Files Modified:**
- `backend/app.py` (oEmbed preview, android/ios, cookiefile, retry removed)
- `pipeline/ingest.py` (cookie helpers, whisper resilience, android/ios)
- `pipeline/chunking.py` (whisper fallback, cookie-aware transcript API)
- `frontend/src/pages/Library.tsx` (preview timeout, modal duration guard)
- `requirements.txt` (openai-whisper)

**Status:** ✅ COMPLETE (reliability fixes shipped; proxy + playlist feature pending)

**Next Steps:**
- Decide on **residential proxy** (Webshare) → wire into yt-dlp + transcript.
- Build **playlist ingestion (resumable) + Playlists tab** (see plan above), proxy-gated.
- Rotate the **exposed HF token** embedded in the git remote.

---

### Session 2 — Revert to Jul 10 baseline + upgrade roadmap captured
**Date:** 2026-07-12
**AI:** GitHub Copilot (agent)
**Context:** A large in-progress feature branch of work (durable jobs, quiz sets, point/range questions, semantic topology, Playwright harness — all built on Jul 12) was **reverted at the user's request**. The user then handed over a set of observed problems + desired upgrades to structure, polish, and plan before any re-implementation.

**What was done:**
1. **Verified production DB is untouched.** Live Supabase project `xucwewnohhucheyqkdjs` still has only the 15 original tables; the Jul-12 tables (`video_ingest_jobs`, `quiz_sets`, `user_quiz_event_state`) do **not** exist and no `20260712…` migration is applied (last applied migration is 6 May). Data intact: 136 videos, 1178 questions, 59 attempts. All Jul-12 migrations had only ever run against a throwaway local Docker pgvector container (since deleted).
2. **Reverted the working tree to Jul 10 commit `23da893`** (`git reset --hard`), deleted the `backup/wip-jul12` branch, and cleaned leftover untracked (`.vscode/`, `frontend/tests/`). No backup retained (per explicit user instruction).
3. **Diagnosed the two direct questions:** (a) Settings slowness root cause = `GET /api/models` makes live Google + OpenRouter calls, sequentially, 15 s timeout each (~30 s worst case), no cache; (b) reminded the chapter quiz strategy = pretest (start) / mid_recall (middle) / end_recall (end).
4. **Captured & structured the user's upgrade observations** into `docs/UPGRADE_BACKLOG.md` (proposed roadmap; nothing implemented yet).

**Key Decisions:**
- Nothing from the reverted Jul-12 session remains in the tree; upgrades will be re-approached **fresh, incrementally, and flag-guarded**, not restored wholesale.
- MUNIMJI records the revert honestly so future sessions know the Jul-12 features are **planned, not shipped**.

**Files Modified:**
- `MUNIMJI.md` (this entry)
- `docs/UPGRADE_BACKLOG.md` (new — structured upgrade requirements)

**Status:** 🔄 IN PROGRESS (planning captured; implementation pending user go-ahead)

**Next Steps (proposed upgrade roadmap — see `docs/UPGRADE_BACKLOG.md`):**
1. Per-video **resume record** (durable stage ledger, not just incremental skip).
2. **Point + time-range** questions (range uses transcript **and** keyframes inside the interval).
3. **Checkpoint quiz = 10 questions, Bloom-ordered** (2-3 low-order first, majority higher-order); fix the current 5-6 shrink.
4. **Previous-question button** on the quiz modal.
5. **Auto-popup quiz at each checkpoint** (currently not firing).
6. **Wrong-option explanations** for every distractor.
7. **Concise, structured answer system prompt** (replace the long-response prompt; progressive depth).
8. **Increase checkpoint interval / cap markers** (reduce clutter).
9. **Incremental/resumable quiz generation** (survive API-quota hits without redoing done checkpoints).
10. **OpenRouter key onboarding guide**.
11. **Fast Settings** (cache model catalogs, fetch providers in parallel, lazy-load, short timeouts).

---

### Session 3 — Implemented all 11 upgrades (incl. production durable-jobs table)
**Date:** 2026-07-12
**AI:** GitHub Copilot (agent)
**Context:** Executed the full `docs/UPGRADE_BACKLOG.md` roadmap incrementally after an interference analysis + priority order. Each item verified before moving on. Built on the Jul-10 baseline (post-revert).

**What was done (all 11):**
1. **Checkpoint interval** (`pipeline/checkpoints.py`) — adaptive spacing (8→20 min by duration) + hard cap of 24 markers. 7-hr video went 50+ → 21.
2. **Fast Settings** (`backend/app.py` `/api/models`) — Google + OpenRouter fetched concurrently, 6 s timeout each (was 15 s sequential), 45-min in-process cache. `frontend` lazy-loads catalogs only when "Advanced" opens.
3. **OpenRouter guide** (`frontend Settings.tsx`) — expandable step-by-step + `sk-or-` / HTTP-402-on-zero-credits note.
4. **Concise system prompt** (`pipeline/answer.py`) — `[difficulty] + TL;DR` first, bullets, one analogy, term etymology; heavy sections (misconceptions/mnemonic/exam/research/Bloom/revision) only on depth request.
5. **Bloom-10 checkpoint quizzes** (`pipeline/quiz_gen.py`) — canonical 10-question plan (1 remember / 2 understand / 3 apply / 2 analyse / 2 evaluate), validated + ordered; stops the 5-6 shrink.
6. **Wrong-option explanations** (`quiz_gen.py` + `quiz_cache.py`) — prompts demand `option_explanations` A/B/C/D + misconception; now stored + returned (was the missing piece). Shared modal already renders them.
7. **Previous-question button** (`ChapterQuizModal.tsx`) — per-question answer persistence, read-only revisit, no resubmit/score change, disabled on Q1.
8. **Auto-popup at checkpoint** (`Watch.tsx`) — the Test-me quiz now auto-pops at each semantic checkpoint (every video has them; most have no chapters, which is why it wasn't firing), pauses with skip/dismiss, once-per-checkpoint, seek-flood guarded.
9. **Point + time-range questions** (`models.py`, `pipeline/rag.py`, `backend/app.py`, `Watch.tsx`) — `AskRequest` scope/start/end + validation (ordered, ≤30 min); range retrieval uses only transcript + keyframes inside `[start,end)`, omits the whole-video digest + live frame; Watch UI Point/Range toggle with mm:ss editing + "now" setters.
10. **Incremental quiz gen** — already resumable at checkpoint granularity (ingest pre-gen skips already-cached checkpoints; batches independent; each caches on completion). Strengthened by item 11's durable record.
11. **Durable per-video resume record** (`backend/processing_jobs.py` + new table) — atomic claim / heartbeat / stage-cursor / owner-token fencing behind `DURABLE_JOBS_V1` (dark). One owner per video; concurrent workers → exactly one runs; expired takeover fences the old owner and resumes from the committed stage.

**Production DB change (at user's explicit request):**
- Applied migration `durable_video_ingest_jobs` **directly to production Supabase** (`xucwewnohhucheyqkdjs`). **Purely additive**: created the new `video_ingest_jobs` table + indexes + RLS (service_role only) and backfilled one row per existing video. **No existing table or row was modified.** Reversible with `DROP TABLE public.video_ingest_jobs`.
- Backfill result: 136 videos → 136 jobs (15 `complete`/ready, 121 resumable — 115 at `transcript`, 6 at `download`). Verified.
- The current production/HF backend (old code) does not read this table, so it is unaffected. The new backend keeps `DURABLE_JOBS_V1=0` until deployed + enabled.

**Key Decisions:**
- Interference map → 3 clusters (quiz-gen 3+6+9, Settings 10+11, Watch 2+4+5) done together; isolated items (8, 7, 1) standalone.
- Auto-popup driven by **checkpoints** (present on every video), not chapters (present on only ~22/136).
- Durable-jobs code stays flag-dark; only the additive table went to production.

**Files Modified:**
- Backend: `app.py`, `models.py`, `pipeline/{checkpoints,answer,quiz_gen,quiz_cache,rag}.py`, new `backend/processing_jobs.py`
- Frontend: `pages/{Settings,Watch}.tsx`, `components/ChapterQuizModal.tsx`, `api/client.ts` (via type), `types/index.ts`
- Docs: `MUNIMJI.md`, `docs/UPGRADE_BACKLOG.md`

**Status:** ✅ COMPLETE (all 11 implemented + verified: 48 hermetic tests, disposable-DB durable-job concurrency/fence tests, frontend build)

**Next Steps:**
- Deploy the new backend + frontend (keep `DURABLE_JOBS_V1=0` at first; enable after canary).
- Optional: surface `get_job` resume state in the video status API for a richer resume UI; make on-demand checkpoint quiz exact-only (drop nearest-cache substitution).
- Commit the local changes (currently uncommitted on `main`).
