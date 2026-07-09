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
