# MANAGER HANDOFF — EduVidQA Product

> **For:** Incoming project manager / tech lead
> **From:** Outgoing owner
> **Date:** 25 April 2026
> **Read time:** ~15 minutes
> **Status:** MVP pipeline shipped on localhost. Ready to productize for multi-tenant launch.

---

## 0. TL;DR — Read this first

You are inheriting a **working single-user MVP** that needs to become a **multi-tenant web product**.

- The hard ML/RAG work is **done and tested**. Don't rebuild it.
- The product work (auth, multi-user DB, deploy, quizzes, landing page) is **not started**. Build it.
- There are **3 leaked API keys in `.env`** — rotate them today, before anything else.
- Total target cost for MVP: **$0/month** using Vercel + Supabase + HF Spaces free tiers.
- Next concrete action: provision Supabase, swap Chroma → pgvector, then ship a landing page + auth.

If you read nothing else, read [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/index.html](docs/index.html) (open in a browser).

---

## 1. What the product is

**EduVidQA** = AI tutor for any YouTube lecture.

A user pastes a lecture URL, watches it, and asks questions in natural language. The system answers using the actual content of the video — text + visuals — and cites the exact timestamps. Every answer is **traceable to a moment in the lecture**. That's the USP vs ChatGPT/Gemini, which give generic textbook answers.

**Vision (the product we're building toward):**

> Anyone signs up → adds a YouTube lecture → gets a traceable AI tutor + interactive checkpoint quizzes + spaced review of missed questions. Every video is processed **exactly once globally** and reused across all users.

Founded on the EMNLP 2025 EduVidQA paper (dataset + Clarity/ECT/UPT metrics). The paper has no product, no RAG, no multimodal frames. We added all of that.

---

## 2. Where things stand

### ✅ Already shipped (don't touch unless broken)

| Component | What it does | Files |
|---|---|---|
| Ingest pipeline | YouTube download (yt-dlp + pytubefix fallback), captions or Whisper, SSIM-deduped keyframes | [pipeline/ingest.py](pipeline/ingest.py), [pipeline/keyframes.py](pipeline/keyframes.py), [pipeline/chunking.py](pipeline/chunking.py) |
| RAG (v2) | Jina CLIP v2 embeddings (text+image same space), Chroma store, timestamp-aware re-rank | [pipeline/rag_v2.py](pipeline/rag_v2.py), [pipeline/embeddings_v2.py](pipeline/embeddings_v2.py) |
| Answer generation | Groq Llama-4 Scout 17B (vision) primary → Gemini 2.0 Flash fallback. Live frame + 3 keyframes + top-10 chunks | [pipeline/answer.py](pipeline/answer.py), [pipeline/live_frame.py](pipeline/live_frame.py), [pipeline/prompts.py](pipeline/prompts.py) |
| Quality scoring | Llama 3.3 70B as judge, scores Clarity/ECT/UPT 1–5 each | [pipeline/evaluate_v2.py](pipeline/evaluate_v2.py) |
| Backend API | FastAPI, 3 endpoints: `/api/health`, `/api/process-video`, `/api/ask`. Auto-ingests on first ask, cached after | [backend/app.py](backend/app.py), [backend/models.py](backend/models.py) |
| Frontend | React + Vite + Tailwind. Single screen — URL paste → embedded YouTube player → chat with timestamp-freeze on focus → markdown answer + quality badges | [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/components/](frontend/src/components/) |
| Tests | Pytest covers each pipeline stage + e2e | [tests/](tests/) |
| Demo videos | Manim explainer v1 → v4 for supervisor pitch | [media/videos/explainer_v3/](media/videos/explainer_v3/), [media/videos/explainer_v4/](media/videos/explainer_v4/) |

5 lectures already indexed in `data/processed/`: `3OmfTIf-SOU`, `VRcixOuG-TU`, `VZYNneIHXJw`, `aircAruvnKk`, `oZgbwa8lvDE`.

**Live behaviour today:** `/api/ask` returns in ~3s on cached video. Tests green.

### 🚧 Not yet built (the work ahead)

- **No auth** — anyone can hit `/api/ask` and burn paid LLM tokens.
- **No multi-user DB** — Chroma is on local disk. A second backend container would re-process every video.
- **No background worker** — heavy ingest runs inside the HTTP request coroutine, blocks event loop.
- **No quiz feature** — the planned checkpoint-quiz + on-demand "Test me" + spaced review system.
- **No real frontend routing** — single screen, no landing page, no library, no /watch/:id.
- **Not deployed publicly** — Dockerfile exists for HF Space but never pushed; Vercel rewrite is broken.

The full gap list with priority tags is in [docs/ROADMAP.md](docs/ROADMAP.md).

---

## 3. Architecture you're inheriting → architecture to build

**Today (single user, localhost):** React → FastAPI → Chroma (local disk) → Groq/Gemini.

**Target:**
- **Frontend:** Vercel (free)
- **Auth + DB + Storage + Realtime:** Supabase (free tier)
- **API + ingest worker:** HF Space Docker or Fly.io (free)
- **LLMs:** Groq + Gemini (free tiers, BYOK fallback for users)

Total cost for MVP: **$0/month**.

**Four invariants you must not break** as the system grows:
1. **Process once globally.** Dedup via `INSERT INTO videos … ON CONFLICT DO NOTHING` on `(video_id, pipeline_version)`. The 1000th user adding the same video pays nothing.
2. **Quiz cache key is global, not per-user:** `(video_id, ts_bucket_30s, prompt_version)`. Two users pausing at the same moment share the same generated quiz.
3. **No long work in HTTP handlers.** Anything >2s goes to a queue (`pgmq` on Supabase) and a worker.
4. **`user_id` is the partition key** on every user-owned row. Single Postgres now, future-shardable mechanically.

Diagrams:
- Technical: [docs/ARCHITECTURE.mmd](docs/ARCHITECTURE.mmd)
- Plain-English (for stakeholders): [docs/ARCHITECTURE_PLAIN.mmd](docs/ARCHITECTURE_PLAIN.mmd)
- Visual tracker: [docs/index.html](docs/index.html)

---

## 4. Critical debt you must address (in this order)

### 🟥 P0 — Do today, before anything else

- **Rotate the 3 leaked keys** in `.env`:
  - `HF_TOKEN` → https://huggingface.co/settings/tokens
  - `GROQ_API_KEY` → https://console.groq.com/keys
  - `GEMINI_API_KEY` → https://aistudio.google.com/apikey
  
  `.env` is gitignored and not in history (`git log --all -p -- .env` returns empty), but ownership has changed hands — assume compromised.

- **Rotate the 3 Supabase secrets** (added 30 Apr 2026 during Session G; pasted in chat during setup, must be considered leaked):
  - `SUPABASE_SERVICE_ROLE_KEY` → API Keys page → 3-dots next to `default` secret key → **Roll secret key**
    - https://supabase.com/dashboard/project/xucwewnohhucheyqkdjs/settings/api-keys
  - `SUPABASE_JWT_SECRET` → JWT Keys page → **Generate new JWT secret** (will invalidate all existing tokens — fine pre-launch)
    - https://supabase.com/dashboard/project/xucwewnohhucheyqkdjs/settings/jwt
  - **Database password** (currently `Supabase@1234` — weak + leaked) → Database settings → **Reset database password** → use a strong random one → update `DATABASE_URL` in `.env` (URL-encode any `@` `:` `/` chars in the password as `%40` `%3A` `%2F`)
    - https://supabase.com/dashboard/project/xucwewnohhucheyqkdjs/database/settings
  - **Personal Access Token** used by the Supabase MCP server (in `~/.config/supabase-pat`, exported via LaunchAgent `com.shubhamkumar.supabase-env`) → Account tokens → **Revoke** old → **Generate new** → write to same file
    - https://supabase.com/dashboard/account/tokens


### 🟥 P1 — Before any public deploy

- Lock CORS in [backend/app.py](backend/app.py). Currently `allow_origins=["*"]` with `allow_credentials=True` (browsers reject the combo, and any origin can call paid endpoints).
- Add Supabase JWT auth on `/api/ask` and `/api/process-video`.
- Stop leaking server errors to clients (`HTTPException(500, detail=str(exc))` patterns leak file paths and SDK errors).
- Fix [vercel.json](vercel.json) rewrite — it uses `${VITE_API_URL}` which Vercel does not expand at runtime.
- Dockerfile runs as root — add a non-root `USER`.

### 🟧 P2 — Silent bugs in production today

- Backend↔frontend contract mismatches (`generation_time_seconds` vs `generation_time`, `ProcessResponse` shape, `HealthResponse.model_name`). Silently breaks the UI. Fix root cause: generate TS types from OpenAPI.
- `_last_error` bug in [pipeline/answer.py](pipeline/answer.py) — referenced before assigned in some branches.

### 🟧 P3 — Code hygiene blocking everything

- **Two parallel pipelines in the repo** (v1 + v2). Delete v1: `pipeline/{rag,embeddings,evaluate,inference,inference_gemini,inference_gemini_video,inference_groq}.py`. Rename v2 → canonical names. Update [backend/app.py](backend/app.py) imports.
- Pin [requirements.txt](requirements.txt) — currently unpinned, builds aren't reproducible.

Full debt list with explanations: [docs/index.html](docs/index.html) → "Known Debt" section.

---

## 5. The roadmap (4 phases)

Detailed in [docs/ROADMAP.md](docs/ROADMAP.md). Summary:

| Phase | Status | What it delivers | Sessions |
|---|---|---|---|
| **0. MVP** | ✅ Done | Single-user pipeline working end-to-end | A–E merged |
| **1. Foundation** | 🟧 Active | Auth, Postgres + pgvector, Storage, worker, dedup, deploy targets picked | A–F + **G ✅** + H + K |
| **2. Productize** | Next | Landing/library/watch/review pages, observability, CI/CD, e2e tests | I + J + L + M + K2 |
| **3. Quiz feature** | Planned | Checkpoint quizzes + on-demand + spaced review | G |
| **4. Polish** | Later | Legal pages, billing, org accounts, public catalog | N + O + Growth |

### Session G — Supabase project + schema + auth → ✅ DONE (30 Apr 2026)

Provisioned and verified end-to-end. See [interfaces/SESSION_G_SPEC.md](interfaces/SESSION_G_SPEC.md) for full audit log.

- **Project:** `xucwewnohhucheyqkdjs` (region `ap-south-1`, free tier, EduvidQA Org)
- **Extensions enabled:** `vector` 0.8.0, `uuid-ossp` 1.1
- **8 tables created with RLS on all:** `videos`, `video_chunks`, `keyframe_embeddings`, `user_videos`, `checkpoints`, `questions`, `quiz_attempts`, `review_queue`
- **Migrations applied (4 total):** `000_enable_extensions`, `001_core_tables_v2`, `002_quiz_tables`, `003_rls_policies_v2` — source of truth in [supabase/migrations/](supabase/migrations/)
- **Storage bucket:** `keyframes` (private)
- **Auth:** Email magic-link enabled (default)
- **Python wiring:** [backend/supabase_config.py](backend/supabase_config.py) → `get_supabase_client()` + `get_database_url()` both verified working from `.venv`
- **`.env` keys filled:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`
- **Connection mode:** Transaction Pooler (`aws-1-ap-south-1.pooler.supabase.com:6543`) — IPv4 supported. Direct host (`db.*.supabase.co:5432`) is IPv6-only on free tier and won't resolve from most networks; use the pooler URL in `.env`.

**Tooling installed for ongoing work:**
- Supabase MCP server registered globally at `~/Library/Application Support/Code/User/mcp.json` — usable from every VS Code workspace
- LaunchAgent `com.shubhamkumar.supabase-env` exports `SUPABASE_ACCESS_TOKEN` from `~/.config/supabase-pat` to all GUI apps on login (survives reboots)
- The MCP can apply migrations, run SQL, list tables, fetch keys, and run security advisors on demand

### Production checklist — what MUST change before public launch

This checklist is specific to the Supabase setup completed in Session G. **Track this as a launch blocker.**

#### A. Secrets & access (mandatory — pre-launch hard block)
1. **Rotate all 4 Supabase secrets** (PAT, service_role, JWT secret, DB password) — see P0 above. They were exposed during interactive setup.
2. **Move secrets to a managed secret store** before deploy:
   - HF Space: Settings → Secrets (not env vars in code)
   - Vercel: Project → Settings → Environment Variables
   - Never commit `.env` (already gitignored — verify still gitignored on every PR)
3. **Strong DB password** (min 24 chars, randomly generated). Update `DATABASE_URL` and re-URL-encode.

#### B. Row-Level Security tightening (Supabase advisor flagged 6 issues)
The current RLS in `003_rls_policies_v2` uses `WITH CHECK (true)` for INSERTs on global tables (`videos`, `video_chunks`, `keyframe_embeddings`, `checkpoints`, `questions`) so the worker can write. This bypasses RLS for those operations. Before launch:
1. Create a dedicated `worker` Postgres role; restrict `INSERT`/`UPDATE` on global tables to `worker` only.
2. Replace `videos_update USING (true)` with `USING (auth.role() = 'service_role')`.
3. Re-run the security advisor: `mcp_supabase_get_advisors --type security` → 0 warnings expected.

#### C. Schema isolation
1. Move `vector` extension out of the `public` schema (advisor warning `extension_in_public`):
   ```sql
   CREATE SCHEMA extensions;
   ALTER EXTENSION vector SET SCHEMA extensions;
   ```
2. Drop the auto-created `public.rls_auto_enable()` SECURITY DEFINER function (advisor flagged it as anon-callable). It is unused in our code.

#### D. pgvector index tuning
1. `ivfflat` with `lists=100` was set assuming ~10k chunks. Re-tune once you have real data:
   - `lists ≈ rows / 1000` (capped at 1000)
   - Consider `hnsw` (better recall, no rebuild on growth) once you exceed ~50k rows.
2. Add `ANALYZE video_chunks; ANALYZE keyframe_embeddings;` to the post-ingest pipeline.

#### E. Free-tier limits to watch (Supabase free)
- **500 MB DB storage** — at 1024-dim vectors × 4 bytes × 2 columns ≈ 8 KB/chunk + text. ~30k chunks before you hit limit. ~150 hours of lecture video. Plan for Pro ($25/mo) at ~100 lectures.
- **1 GB Storage bucket** — keyframes are JPEG, ~100 KB avg. Limit: ~10k frames. Move to S3/R2 (free tier 10 GB) before you scale.
- **2 GB egress / month** — fine for dev, will pinch at ~500 MAU. Add CloudFlare in front before it bites.
- **Project pauses after 7 days of inactivity** on free tier. Set up a heartbeat (cron-ping `/api/health` every 6 days) or upgrade.

#### F. Connection pooling
- We're using **transaction pooler** (`:6543`) which does NOT support `LISTEN/NOTIFY` or session-level features. If you add Supabase Realtime later, switch the relevant connections to **session pooler** (`:5432`) or use the JS client with the publishable key.

#### G. Backups
- Free tier: **7-day point-in-time recovery is NOT included** — only daily logical backups via dashboard. Before launch:
  - Export schema weekly: `pg_dump --schema-only` to a private GitHub repo
  - For Pro ($25/mo) you get PITR; budget for it before opening signups

#### H. Monitoring
- Hook the [Supabase logs](https://supabase.com/dashboard/project/xucwewnohhucheyqkdjs/logs/explorer) into Sentry/Logtail before launch
- Set up an alert on `auth.users` row growth (signup spike = potential abuse)
- Dashboard → Reports → enable email digest

**Suggested execution order for a manager:**

1. **Day 1:** Rotate keys. Read [HANDOFF.md](HANDOFF.md), [docs/ROADMAP.md](docs/ROADMAP.md), open [docs/index.html](docs/index.html) in browser.
2. **Week 1:** Provision Supabase free project. Enable `pgvector` + `pgmq` extensions. Design schema (videos, video_chunks, user_videos, checkpoints, questions, quiz_attempts, review_queue). Write RLS policies.
3. **Week 2:** Swap Chroma → pgvector in [pipeline/rag_v2.py](pipeline/rag_v2.py). Migrate the 5 indexed videos. Move keyframes to Supabase Storage.
4. **Week 3:** Add Supabase Auth on backend (verify JWT). Add background worker (start with FastAPI `BackgroundTasks`, graduate to `pgmq`).
5. **Week 4:** Frontend routing (`react-router-dom`), landing page, login, library page, auth context.
6. **Week 5:** Deploy backend to HF Space, frontend to Vercel. Sentry, structured logs, basic e2e Playwright test.
7. **Week 6+:** Quiz feature (Phase 3).

**MVP cut for a fast public beta:** skip pgmq (use FastAPI `BackgroundTasks`), skip realtime (poll every 2s), skip pre-generated checkpoint quizzes (generate on first viewer), skip full SRS (just store missed Qs).

---

## 6. Stack & decisions you're inheriting

**Don't change these without a strong reason — they were tested and chosen carefully.**

| Layer | Pick | Why |
|---|---|---|
| Primary VLM | Groq Llama-4 Scout 17B (vision) | Fast (~3s), free tier, vision-capable |
| Fallback VLM | Gemini 2.0 Flash | Independent provider for resilience |
| Judge model | Groq Llama 3.3 70B | Free, big enough to score reliably |
| Embeddings | Jina CLIP v2 (1024-dim) | Local, text+image same space, no API cost |
| Vector store now | Chroma (local) | Was the simplest start |
| Vector store target | Postgres + pgvector | One DB to operate, scales to ~10M vectors |
| DB / Auth / Storage | Supabase | Free tier covers MVP, RLS solves authz |
| Frontend host | Vercel | You already have a `vercel.json` |
| API host | HF Space (Docker) | Free CPU forever, you have a Dockerfile |
| Frontend stack | React 18 + Vite + Tailwind + TS | Already built |

**Models that did NOT work / were considered and rejected** (saves you the experiment):
- Gemini 2.5/3.x video upload — works for some flash variants only; 2.0/2.5/3-pro all hit 429/503 on free tier. See [HANDOFF.md](HANDOFF.md) §14.
- Qwen2.5-VL-7B local on M2 — listed in old plans, never adopted; Groq vision is faster + free.
- BGE-M3 embeddings — replaced by Jina CLIP v2 because we need image embeddings in the same space.

---

## 7. Important: the user's product instincts (already validated with them)

The owner has thought through these and aligned on the following:

1. **Quiz "checkpoints" must be non-blocking.** Not modal. Marker on timeline + soft toast on natural pause near checkpoint. No pop-ups when seeking backward.
2. **A user can self-test anytime** ("Test me" button), not gated behind crossing a checkpoint first.
3. **Quiz cache is global**, not per-user. This is the cost-saver.
4. **Auto-checkpoint quizzes are pre-generated at ingest** so first viewer never waits.
5. **Same YouTube URL from a second user must NOT re-process** — single source of truth in Postgres `videos` table, dedup via atomic `INSERT … ON CONFLICT`.
6. **MVP is $0/month.** Vercel + Supabase + HF Spaces free tiers. No paid services until there's traffic.
7. **Future scale matters now.** Schema decisions (UUIDs, `user_id` partition key, prompt_version cache key) are made up-front so we don't repaint later.

If you're proposing a change to any of these, talk to the owner first.

---

## 8. Files you'll work with constantly

```
eduvidqa-product/
├── HANDOFF_MANAGER.md          ← you are here
├── HANDOFF.md                  ← detailed technical handoff (longer, more code-level)
├── docs/
│   ├── index.html              ← visual tracker — open in browser
│   ├── ROADMAP.md              ← full priority-tagged checklist
│   ├── ARCHITECTURE.mmd        ← target system diagram (technical)
│   └── ARCHITECTURE_PLAIN.mmd  ← same diagram in plain English
├── backend/app.py              ← FastAPI entrypoint
├── pipeline/
│   ├── rag_v2.py               ← biggest file you'll change (Chroma → pgvector)
│   ├── answer.py               ← LLM call orchestration
│   └── (delete the v1 files)
├── frontend/src/
│   ├── App.tsx                 ← single-screen UI (becomes /watch route)
│   └── components/             ← reusable UI parts
├── tests/                      ← pytest suite, keep green
├── .env                        ← LEAKED KEYS LIVE HERE — rotate
├── Dockerfile                  ← HF Space deploy target
└── vercel.json                 ← Vercel config (rewrite is broken, fix)
```

---

## 9. Quick-start commands

```bash
cd /Users/shubhamkumar/eduvidqa-product

# 1. Activate the venv
source .venv/bin/activate

# 2. Run the backend
uvicorn backend.app:app --reload --port 8000

# 3. Run the frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173

# 4. Run the test suite
pytest -q

# 5. Mock-mode frontend (no backend needed)
# set VITE_MOCK_API=true in frontend/.env

# 6. Sanity check
curl http://localhost:8000/api/health
```

---

## 10. Who knows what (escalation map)

- **Product/UX decisions** → owner (the user who handed this over).
- **Paper / metrics / dataset** → EMNLP 2025 paper authors (`https://sr7-human.github.io/eduvidqa-explained/`).
- **LLM provider quirks** → see [HANDOFF.md](HANDOFF.md) §14 for tested model behaviours.
- **Manim explainer videos** → all source in [scripts/explainer_v3.py](scripts/explainer_v3.py) and v4 scenes; render commands in HANDOFF §14.

---

## 11. What "done" looks like for you (manager success criteria)

By the end of your tenure, the project should:

1. ✅ Have the 3 keys rotated and `.env` confirmed clean.
2. ✅ Have a public URL anyone can sign up at.
3. ✅ Process a new YouTube video for any signed-up user, dedup'd globally.
4. ✅ Pass automated e2e: signup → add video → ask question → take quiz → see review queue.
5. ✅ Run on free-tier infra at $0/month.
6. ✅ Have observability: you can see error rate, p95 latency, LLM cost per day, cache hit rate.
7. ✅ Have a CI pipeline that blocks merges on failing tests.
8. ✅ Have a README that lets a new dev set up in <30 min.

---

## 12. First-day checklist for you

- [ ] Read this doc end-to-end.
- [ ] Open [docs/index.html](docs/index.html) in a browser.
- [ ] Skim [docs/ROADMAP.md](docs/ROADMAP.md).
- [ ] Skim [HANDOFF.md](HANDOFF.md) (the older detailed one — long but everything is in there).
- [ ] **Rotate the 3 keys in `.env`. Update `.env`. Test that `/api/ask` still works.**
- [ ] Run the test suite locally — confirm green.
- [ ] Run the backend + frontend locally — confirm you can ask a question on a cached video.
- [ ] Sign up for free Supabase, Vercel, HF accounts if you don't have them.
- [ ] Schedule 30 min with the owner to confirm the priorities in [docs/ROADMAP.md](docs/ROADMAP.md).

Welcome aboard. The hard ML/research work is done. What's left is craft, plumbing, and shipping. Good luck.

— Outgoing owner
