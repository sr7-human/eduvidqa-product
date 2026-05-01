# EduVidQA — Handoff, Findings & Fix Plan

> Written 17 Apr 2026 by the incoming owner's assistant after a cold read of the repo.
> Previous owner left no handoff doc. This file is both a **project snapshot** and
> a **prioritised fix list** to hand to the next coding session.

---

## 0. TL;DR

- Two folders on disk. Actual product code: **`/Users/shubhamkumar/eduvidqa-product`**.
  Sibling `/Users/shubhamkumar/EduVidQA` is just paper/diagrams/website.
- State: single commit `7a0b6ac MVP complete: Multimodal RAG pipeline for YouTube lecture QA` on `main`. "MVP done", not mid-flight.
- Stack: FastAPI backend + React/Vite/Tailwind frontend + Python ML pipeline (Chroma + Jina/Gemini embeddings + Groq Llama-4 / Gemini 2.0 Flash).
- **3 live API keys in `.env` on disk → rotate before anything else.**
- Two parallel implementations (`rag.py` vs `rag_v2.py`, etc.) — one must go.
- Several backend↔frontend contract mismatches silently dropping fields in the UI.
- No auth, no rate limiting, CORS `*` — do not expose the API publicly until fixed.

---

## 1. Repository layout

```
/Users/shubhamkumar/eduvidqa-product/
├── backend/                 FastAPI app (the real entrypoint)
│   ├── app.py               3 endpoints: /api/health, /api/process-video, /api/ask
│   ├── config.py            env-driven Settings
│   └── models.py            Pydantic request/response models
├── pipeline/                Python ML pipeline
│   ├── ingest.py            YT id parse, transcript (captions → Whisper fallback)
│   ├── keyframes.py         SSIM-based frame dedup, adaptive second pass
│   ├── chunking.py          10s transcript windows linked to keyframes
│   ├── digest.py            Gemini one-shot "lecture digest"
│   ├── embeddings_v2.py     Jina CLIP v2 (local) OR Gemini Embedding 2 (API)
│   ├── rag_v2.py            Chroma index + retrieval (timestamp re-rank)
│   ├── live_frame.py        Exact-frame extraction at ask-time
│   ├── answer.py            Groq (primary) → Gemini (fallback) VLM call
│   ├── evaluate_v2.py       Clarity/ECT/UPT scoring via Groq Llama 3.3 70B
│   ├── prompts.py, models.py
│   └── [LEGACY] rag.py, embeddings.py, evaluate.py,
│                inference.py, inference_gemini.py,
│                inference_gemini_video.py, inference_groq.py
├── frontend/                React + Vite + Tailwind
│   ├── src/App.tsx          Single screen, 60/40 split
│   ├── src/api/client.ts    fetch wrapper + mock mode
│   ├── src/components/      YouTubePlayer, ChatInterface, SettingsModal, etc.
│   ├── src/hooks/useAskQuestion.ts   (unused)
│   ├── src/types/index.ts
│   └── .env                 VITE_API_URL, VITE_MOCK_API
├── app_gradio.py            HF Space entrypoint — imports the LEGACY v1 pipeline
├── Dockerfile               python:3.10-slim → uvicorn on 7860 (for HF Spaces)
├── README_HF.md             HF Space frontmatter + minimal README
├── requirements.txt         Unpinned deps
├── vercel.json              Vite build + /api rewrite (see §6 — likely broken)
├── pyrightconfig.json
├── .env                     ⚠ contains live HF / Groq / Gemini keys
├── .gitignore               .env is ignored (confirmed not in git history)
├── tests/                   pytest suite per pipeline stage + e2e
├── scripts/                 one-off migration runners (safe to archive)
├── notebooks/               inference_kaggle.ipynb (one-off)
├── data/                    Chroma db + processed/ per video_id
└── docs/                    only index.html remains (SESSION_*_SPEC.md were deleted)
```

Sibling workspace `/Users/shubhamkumar/EduVidQA/` — paper-explained.md, diagrams/,
website/, tracker.html, sample processed data for `3OmfTIf-SOU`. **Not** the app.

---

## 2. How the system works (end-to-end)

1. **Frontend** (`App.tsx`) — user pastes a YouTube URL, plays it in an embedded
   player. Focusing the chat input auto-freezes the current timestamp. On submit,
   POSTs `{youtube_url, timestamp, question, skip_quality_eval}` to `/api/ask`.
   If the user saved a Gemini key in the Settings modal, it is sent as
   `X-Gemini-Key` header (stored in `localStorage`).
2. **Backend `/api/ask`** (`backend/app.py`):
   - `parse_video_id()` validates the 11-char id.
   - If not indexed → calls `/api/process-video` inline (auto-ingest).
   - `live_frame.extract_live_frame()` grabs the exact-timestamp frame from
     the cached `.mp4`, else nearest stored keyframe.
   - `LectureIndex.retrieve()` — semantic search in Chroma (filtered by
     `video_id`), then re-ranks chunks by timestamp proximity.
   - `answer.generate_answer()` — assembles digest + top 10 chunks + up to 4
     images (live frame + 3 keyframes), calls **Groq Llama-4-Scout-17B** (vision).
     On failure, falls back to **Gemini 2.0 Flash**.
   - If `skip_quality_eval=false`, `evaluate_v2.score_answer()` rates Clarity /
     ECT / UPT 1-5 using Groq Llama 3.3 70B as judge.
3. **Backend `/api/process-video`**:
   - yt-dlp (360p) → pytubefix fallback.
   - `keyframes.extract_keyframes()` (SSIM 0.92, adaptive re-run if >10 kf/min).
   - `chunking.chunk_transcript()` links chunks to overlapping keyframes.
   - `digest.generate_digest()` via Gemini (non-fatal).
   - `LectureIndex.index_video()` upserts chunks + keyframe image embeddings +
     digest into Chroma collection `eduvidqa_jina` or `eduvidqa_gemini`.
   - Deletes the `.mp4` after indexing to save disk.

Embedding choice is set at `LectureIndex(embedding_model=…)` — defaults to
`"jina"` (local, 1024-dim, text+image same space). Chroma uses cosine distance.

---

## 3. Deployment topology (as configured)

- **Backend** → HuggingFace Spaces via Docker (`Dockerfile` + `README_HF.md`
  frontmatter), port 7860.
- **Frontend** → Vercel (`vercel.json`). `/api/*` is rewritten to
  `${VITE_API_URL}/api/*` (but see §6 — this interpolation does not actually
  work the way it's written).
- **Gradio UI** (`app_gradio.py`) — alternative single-file UI, imports the
  legacy v1 pipeline. Currently drifted from the v2 backend.

---

## 4. What's already working

- Ingest → keyframes → chunking → digest → index path runs end-to-end on the
  5 videos currently in `data/processed/` (`3OmfTIf-SOU`, `UHBmv7qCey4`,
  `_PwhiWxHK8o`, `VRcixOuG-TU`, `VZYNneIHXJw`, `aircAruvnKk`, `oZgbwa8lvDE`).
- Chroma persistent store exists under `data/chroma/`.
- React UI renders markdown answers, quality badges, source timestamps, BYOK
  Gemini modal, timestamp freeze-on-focus.
- Mock mode (`VITE_MOCK_API=true`) returns a canned response — lets you work on
  UI without the backend running.
- Pytest suite covers each pipeline stage plus an e2e v2 test.

---

## 5. Issues found (prioritised fix list for the other session)

> Order matters. Do **P0** before touching anything else, then work top-down.

### P0 — Secrets / do this first
- [ ] **Rotate all three keys** in `.env` and anywhere they were ever shared:
  - `HF_TOKEN` → https://huggingface.co/settings/tokens
  - `GROQ_API_KEY` → https://console.groq.com/keys
  - `GEMINI_API_KEY` → https://aistudio.google.com/apikey
  `.env` is `.gitignore`d and `git ls-files` confirms it is **not** in history,
  but assume the keys are compromised since ownership changed hands.
- [ ] Confirm `.env` is not present in any dangling stash, HF Space secret, or
  Vercel env var under the old owner's account.

### P1 — Security / abuse prevention (before any public deploy)
- [ ] **Lock CORS.** `backend/app.py` uses `allow_origins=["*"]` together with
  `allow_credentials=True` — browsers reject this combo and it lets any origin
  call the paid LLM endpoints. Set `CORS_ORIGINS` to the Vercel domain(s) only.
- [ ] **Add authentication** to `/api/ask` and `/api/process-video`. Even a
  single shared API key via header (`X-EduVidQA-Key`) is enough for MVP.
- [ ] **Add rate limiting** (`slowapi` or similar) — per-IP and per-key caps.
  Both endpoints trigger paid LLM calls; `/api/process-video` also pulls a
  video from YouTube and writes to disk.
- [ ] **Stop leaking server errors to the client.** Several paths do
  `HTTPException(status_code=500, detail=str(exc))`. Return a generic message
  and log the full exception server-side only.
- [ ] **Cap input sizes** at the Pydantic layer: `question` max 2 KB, reject
  `timestamp` > 6 hours, validate `youtube_url` with the same regex as
  `parse_video_id` before doing any work.
- [ ] **Fix BYOK copy** in `frontend/src/components/SettingsModal.tsx`. It says
  "never sent to our server" — the key **is** sent as `X-Gemini-Key` on every
  request. Either change wording to "not stored on our server" or proxy so it
  really isn't.

### P2 — Correctness / contract bugs (silent UI breakage today)
- [ ] **`generation_time` mismatch.** Backend returns `generation_time_seconds`
  (`backend/models.py` `AskResponse`); frontend reads `res.generation_time`
  (`frontend/src/types/index.ts`, `frontend/src/App.tsx`). Result: "Time: —" in
  the UI forever. Align on one name (suggest `generation_time_seconds`
  everywhere, update the type).
- [ ] **`ProcessResponse` mismatch.** Backend returns `{video_id, title,
  duration, segment_count, message}`; frontend type declares `status:
  'processed' | 'already_cached'`. Pick one.
- [ ] **`HealthResponse` mismatch.** Backend includes `model_name`; frontend
  type omits it. `checkHealth()` mock also omits it.
- [ ] **`/api/health` dead code.** Computes `indexed_count` then throws it
  away. Either return it (add to `HealthResponse`) or delete the block.
- [ ] **`_last_error` bug in `pipeline/answer.py`.** Assigned inside the Groq
  `except` block but referenced in the final `raise` without being defined if
  only `gemini_key` path failed cleanly. Initialise `_last_error = None` at top
  of `generate_answer`.
- [ ] **Vercel rewrite is almost certainly broken.** `vercel.json` has
  `"destination": "${VITE_API_URL}/api/:path*"` — Vercel does not expand
  `VITE_*` env vars in rewrites at runtime. The client already uses
  `import.meta.env.VITE_API_URL` at build time, so the rewrite is redundant
  and misleading. Either hardcode the destination or delete the rewrite and
  rely on the build-time API URL.

### P3 — Architecture / code hygiene
- [ ] **Delete the v1 pipeline.** Keep only `rag_v2.py`, `embeddings_v2.py`,
  `evaluate_v2.py`, `answer.py`. Remove `rag.py`, `embeddings.py`,
  `evaluate.py`, `inference.py`, `inference_gemini.py`,
  `inference_gemini_video.py`, `inference_groq.py`. Update `app_gradio.py`
  to use v2 (or delete it if the HF Space isn't needed).
- [ ] **Rename v2 → canonical names** after the delete (`rag_v2.py` → `rag.py`,
  etc.). Update imports in `backend/app.py`, tests, scripts.
- [ ] **`process-video` blocks the event loop.** It's `async def` but does
  synchronous yt-dlp / OpenCV / SSIM / embedding / Chroma work on the request
  coroutine. Wrap heavy calls in `asyncio.to_thread()` or move to a
  background task (FastAPI `BackgroundTasks` / a small queue).
- [ ] **Pin `requirements.txt`.** Every line is unpinned; builds are
  unreproducible and a breaking release in any transitive dep will silently
  break HF Space builds. Pin with `pip-compile` or at minimum `==` on
  `torch`, `transformers`, `chromadb`, `sentence-transformers`.
- [ ] **Dockerfile runs as root.** Add a non-root `USER`, set `WORKDIR`
  permissions accordingly.
- [ ] **Runtime monkey-patch of cached Jina EVA model**
  (`pipeline/embeddings_v2.py::_patch_jina_eva_model`) is fragile — any HF
  cache refresh or newer model revision silently re-breaks it. Options: pin
  `torch<2.11` explicitly, fork the model, or at minimum log an error instead
  of silently no-op'ing when the needle is missing.

### P4 — Cleanup
- [ ] Delete unused frontend code: `components/VideoInput.tsx`,
  `hooks/useAskQuestion.ts`, and the `@tanstack/react-query` dependency.
- [ ] Move `DEFAULT_VIDEO_URL` out of `App.tsx` into an env var.
- [ ] `docs/` only contains `index.html`; `SESSION_*_SPEC.md` referenced in
  the workspace index are gone. Either restore from git history
  (`git show 16178d4:docs/SESSION_A_SPEC.md` etc.) or remove the placeholder.
- [ ] Archive `scripts/` one-off migration runners into `scripts/archive/`.

---

## 6. Things I did **not** verify (worth poking at)

- Whether the HF Space is actually deployed and under whose account.
- Whether the Vercel project exists, what domain it's on, and which env vars
  are set there.
- Whether the old owner's Groq/Gemini/HF accounts still have these keys bound
  to shared billing.
- Whether `data/chroma/` contents are considered canonical or disposable —
  re-indexing all 7 videos takes non-trivial time + API quota.

---

# 7. Post-fix audit plan

Run this **after** the other session finishes P0–P2 (minimum) and claims done.
Each step has a pass/fail check so results are objective.

### Phase A — Secrets & repo hygiene
1. `git log --all -p -- .env` → must be empty.
2. `rg -n "gsk_|AIza|hf_[A-Za-z0-9]{30,}" -S` across the whole repo (including
   `frontend/`, `notebooks/`, `docs/`, `tracker/`) → must return zero hits
   outside `.env`.
3. Verify every rotated key works by hitting a trivial endpoint on each
   provider with a plain `curl`; confirm the old keys are revoked (401).
4. `git ls-files | xargs grep -l "TODO\|FIXME\|XXX"` → triage each remaining one.

### Phase B — Contract parity (backend ↔ frontend)
5. Generate an OpenAPI schema: `curl http://localhost:8000/openapi.json > /tmp/oai.json`.
6. Spot-check every field in every response is consumed by the frontend. Use:
   `rg -n "\.(answer|sources|quality_scores|model_name|generation_time|generation_time_seconds|video_id|title|duration|segment_count|message|status|indexed_count)" frontend/src`.
7. In the browser devtools, send one real `/api/ask` → confirm **every**
   field in `AskResponse` renders somewhere (or is intentionally ignored).
8. Run `npm run build` — it runs `tsc` first, so any type mismatch introduced
   by the fixes will fail the build. Zero errors required.

### Phase C — Security smoke tests
9. CORS: from `https://example.com` devtools console, `fetch('<api>/api/health')` →
   must be **blocked** in prod config.
10. Auth: `curl -XPOST <api>/api/ask -d '{}'` without the API key header →
    must return 401/403, not 422/500.
11. Rate limit: loop 50 requests in 10s with a valid key → must get 429 before
    finishing.
12. Error leak: force an internal exception (e.g. malformed URL that passes
    regex but fails downstream) → response body must **not** contain file
    paths, stack frames, or provider SDK error text.
13. Input caps: POST a 50 KB `question` → 422 with a clean validation error.
14. Verify BYOK header path: with a bogus `X-Gemini-Key`, a Groq outage should
    surface "invalid Gemini key" — not a 500.

### Phase D — Runtime behaviour
15. Cold start `uvicorn backend.app:app --port 8000` with `LAZY_LOAD=true` →
    `/api/health` must respond in <1s.
16. Full happy path on a fresh video (not in `data/processed/`):
    - `POST /api/process-video` → 200, ≤ reasonable time, `.mp4` deleted,
      `data/chroma/` count increased.
    - `POST /api/ask` → 200, `sources` non-empty, `quality_scores` present
      when `skip_quality_eval=false`, `generation_time_seconds` > 0.
17. Cached-video path: second `POST /api/ask` on the same video — latency
    must drop significantly (no re-ingest).
18. Concurrency: 3 parallel `/api/ask` calls on 3 different videos → no
    500s, no event-loop stalls (each should complete in roughly its own
    serial time, proving `to_thread` or background task works).
19. Failure modes: kill the network mid-Groq call → Gemini fallback path
    must engage and return a valid answer.

### Phase E — Pipeline correctness
20. `pytest -q` — full suite green.
21. `pytest tests/test_e2e_v2.py -q` specifically must pass against a real
    (not mocked) backend.
22. For one known video, diff the new retrieval output (chunk ids, order,
    similarities) against a pre-fix capture → should be unchanged except
    where retrieval code itself was touched.
23. Quality scores sanity check: run `evaluate_v2.score_answer` on 10 known
    (question, answer) pairs → all scores in [1,5], JSON parses, no 500s.

### Phase F — Deploy checks
24. Build the Docker image: `docker build -t eduvidqa . && docker run --rm -p 7860:7860 --env-file .env eduvidqa` → `/api/health` reachable.
25. Image must not run as root: `docker exec <id> whoami` ≠ `root`.
26. `npm run build` in `frontend/` produces `dist/`; serve it with
    `npm run preview` pointed at the local backend → full happy-path works.
27. Vercel rewrite (if kept): deploy a preview, confirm `/api/health` on the
    Vercel domain forwards correctly.

### Phase G — Docs
28. Update `README.md` / `README_HF.md` to reflect the single pipeline
    (v2), the auth model, the CORS config, and the real env var list.
29. This `HANDOFF.md` should be replaced by a standing `ARCHITECTURE.md`
    once the fixes land — keep the audit plan under `docs/AUDIT.md`.

---

## 8. Quick-start for the new owner

```bash
# 0. Rotate keys first, update .env
cd /Users/shubhamkumar/eduvidqa-product

# 1. Python env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Backend
uvicorn backend.app:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173, proxies /api to :8000

# 4. Mock mode (no backend needed)
# set VITE_MOCK_API=true in frontend/.env
```

Sanity check:
```bash
curl http://localhost:8000/api/health
```

---

## 14. Post-handoff updates (22 Apr 2026)

Updates made after the original handoff was written. Doc body above is otherwise unchanged.

### Gemini video upload — myth busted
- Original handoff implied Gemini video upload "hangs on free tier".
- Re-tested: upload itself takes ~6.6 s + ~10 s polling to ACTIVE for a 5 MB file. Not hanging.
- Failures were **model-specific** transient errors, not the upload path:
  - 429 / quota: `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-3-pro-preview`, `gemini-3.1-pro-preview`
  - 503: `gemini-2.5-flash`
  - **Working** (free tier, video Q&A): `gemini-flash-latest` (~7–13 s), `gemini-3-flash-preview` (~11.6 s), `gemini-3.1-flash-lite-preview` (~9.1 s)
- **Patched** [`pipeline/inference_gemini_video.py`](pipeline/inference_gemini_video.py) line 19: `gemini-2.5-flash` → `gemini-3-flash-preview`.
- Recommend: when bumping models elsewhere in the codebase, prefer `gemini-flash-latest` or `gemini-3-flash-preview` over any 2.x.

### Manim explainer videos (demo for supervisor → edtech forward)
Three iterations of a Manim explainer were produced. Final = **v3**.

| Version | Source | Render | Duration | Notes |
|---|---|---|---|---|
| v1 | `scripts/explainer.py` | `media/videos/explainer/480p15/EduVidQAExplainer.mp4` | 90.5 s | First pass. Pipeline overview only. |
| v2 | `scripts/explainer_v2.py` | `media/videos/explainer_v2/720p30/EduVidQAExplainer.mp4` | 90 s | Added USP-focused split-screen scene (ChatGPT vs EduVidQA). |
| **v3** | [`scripts/explainer_v3.py`](scripts/explainer_v3.py) | [`media/videos/explainer_v3/720p30/EduVidQAExplainer.mp4`](media/videos/explainer_v3/720p30/EduVidQAExplainer.mp4) | **112.8 s** (1:53) | Integrated. 7 scenes: title → problem → 3-stage overview → ingest+index zoom → ask zoom (timeline + retrieval + VLM) → ChatGPT vs EduVidQA split-screen → CTA. |

USP framing locked in: **"Every answer is traceable to a moment in the lecture"** — demonstrated via timestamp-grounded answers + clickable `[mm:ss]` citations, contrasted against ChatGPT's generic textbook reply on the same lecture-specific question.

To re-render:
```bash
manim -ql scripts/explainer_v3.py EduVidQAExplainer   # 480p15 preview
manim -qm scripts/explainer_v3.py EduVidQAExplainer   # 720p30 demo
manim -qh scripts/explainer_v3.py EduVidQAExplainer   # 1080p60 final
```

### Live status (re-verified 22 Apr)
- ✅ Backend `/api/ask` returns in ~3 s on cached video (same as 17 Apr).
- ✅ Tests still pass: `tests/test_ingest.py tests/test_rag.py tests/test_inference.py`.
- ✅ Chroma collections unchanged: `eduvidqa_jina` 1824 items, `eduvidqa_gemini` 792.

### Still open from original handoff (unchanged)
- Public deployment URL (HF Space / Vercel) — not done.
- Tracker `/Users/shubhamkumar/EduVidQA/tracker.html` — not updated with above.
- Accuracy regression (ECT 2/5 on two live runs) — not investigated.
- API key rotation — **still required**, not done.


--------new-Drama---------

## My honest take first

**I like it. A lot. But it has real risks worth naming up front.**

### Why it works
- **Fixes the actual root cause of "laggy":** the v3 feels slideshowy because the *camera has no subject*. Boxes appear, arrows move, text fades — your eye has nowhere to follow. Characters walking across a continuous floorplan give every frame a subject. Pacing fixes itself.
- **The metaphor is structurally honest, not decorative.** It maps 1:1 to your real architecture:
  - Waiter ↔ FastAPI (transport, never cooks)
  - Library ↔ Chroma vector store (indexed, addressable)
  - Embedding ↔ "walking to the right drawer's coordinates"
  - Re-rank by timestamp ↔ tray reshuffle
  - VLM ↔ Chef who *looks at* both ingredients (text + image)
  - Evaluator ↔ Food Critic. This one is *perfect* — judge models literally are food critics.
  - Live frame ↔ "fresh catch from the freezer at exactly 04:32" — sells the timestamp-precision USP without a single bullet point.
- **Two-act structure is forced by your design** (`/api/process-video` is genuinely a different time from `/api/ask`). Most explainers fudge this. Yours can show it cleanly: empty restaurant → service.
- **The USP scene gets way stronger.** Instead of "ChatGPT vs us" as two split panels of text, it's "two doors on the same street, same customer, same question, two dishes." Visceral.

### Risks I'd flag now (cheaper to fix in script than in render)
1. **Cute vs credible.** A pi-creature restaurant could read as "kids' content" to a research supervisor. Mitigation: every character gets a **lower-third tech label** the first time they appear (e.g. `Maitre — FastAPI router`, `Indie — Chroma + Jina CLIP v2`). The metaphor sells the *flow*; the labels keep the rigor.
2. **Don't narrate the metaphor.** Narrator should talk about the *system*. Characters' actions carry the metaphor silently. If the VO ever says "the waiter brings the order to the kitchen", we've failed — say "the request is routed to the retriever." Let the visual do the metaphor work.
3. **Speech bubbles are dangerous.** They invite reading, which kills pace. Rule: ≤ 5 words, ≤ 2 bubbles per scene, only at moments of *character intent* ("Order up!", "Coordinates: [0.12, –0.44]").
4. **One visual register, not two.** Pick either "warm storybook restaurant" *or* "3b1b dark-bg with pi-creatures-as-staff". Mixing them looks amateur. **My pick: dark 3b1b background, characters in soft pastel — keeps the mathy seriousness, gains the warmth.**
5. **Length budget.** No hard cap, but every scene should *do work*. I'm budgeting ~3:00–3:30 across 4 acts. If a scene doesn't show something the audience didn't already understand, cut it.
6. **Prep Act is dangerous to dwell on.** The audience cares about asking questions, not about ingestion. Treat Act I as a brisk cold-open (~30 s), not a tutorial.

### One refinement I'd push for
Make the **order ticket** the recurring camera anchor. The ticket is *physical, paper, has the question + timestamp printed on it*. The camera follows the ticket: from printer → Maitre's hand → Indie's reading desk → kitchen counter → next to the plate when served. When the answer comes back, the ticket is **stapled to the back of the dish**, and the [mm:ss] citations on the plate visually **match** the timestamp on the ticket. That single prop carries the entire "traceability" USP without a single label.

---

Now the full script. Dark background (3b1b style), characters as soft-pastel pi-creature variants. Camera describes what's on screen; **VO** is the narrator voiceover; **bubble** is character speech (short, on-screen text bubble); **label** is a lower-third tech tag.

---

# EduVidQA — *Kitchen Tour*  (working title)
**Target:** ~3:15. Dark background. Continuous floorplan: pantry (left) → vector library (center) → kitchen (right) → dining table (front). Camera pans/zooms across this single set; never cuts to black.

## Cast

| Character | Role | Color | Tech label (lower-third on first appearance) |
|---|---|---|---|
| **Maitre** | Waiter | green | `FastAPI · backend/app.py` |
| **Quill** | Scribe | blue | `Transcript chunker · pipeline/chunking.py` |
| **Lens** | Photographer | orange | `Keyframe extractor · SSIM dedup` |
| **Indie** | Librarian | purple | `Chroma + Jina CLIP v2 embeddings` |
| **Chef Vee** | Vision Chef | red | `Groq Llama-4 Scout · vision-language model` |
| **Critic** | Food Critic | white | `Llama 3.3 70B · LLM-as-judge` |
| **Customer (You)** | The student | yellow | (no label) |

Recurring prop: **the order ticket** — small white paper card, printed with `Q: …` / `t = 04:32` / `video: 3OmfTIf-SOU`.

---

## ACT I — *Prep Day*  (~30 s)
*Goal: show that ingestion happens once, ahead of time, so the audience knows Act II isn't doing all this work live.*

### Scene 1 — Cold open  (0:00 – 0:08)
**Visual:** Pitch black. A neon sign flickers on, top-center: **"EduVidQA — Open Kitchen."** The kitchen floorplan dim-lit behind it. A small delivery truck rolls in from screen-left and drops a film canister labeled `lecture.mp4` at the back door. Sign brightens.
**VO:** "Most AI tutors answer from a textbook they read once, somewhere. *Ours* prepares the lecture itself — before you ever ask."

### Scene 2 — Quill chunks the transcript  (0:08 – 0:18)
**Visual:** Quill walks in carrying the canister. Unrolls it on a long table — it becomes a horizontal **ribbon of transcript text** with a parallel **strip of video frames** above it. Quill produces oversized scissors and snips the ribbon every 10 seconds. Each piece falls into a tray, stamped `[02:10 → 02:20]`, `[02:20 → 02:30]`...
**Label:** `Quill — Transcript chunker · pipeline/chunking.py`
**VO:** "First, the lecture is sliced into ten-second windows of text — small enough to retrieve precisely, big enough to carry context."

### Scene 3 — Lens picks keyframes  (0:18 – 0:30)
**Visual:** Lens walks the frame strip with a magnifying glass labeled **"SSIM"**. Holds two adjacent frames side by side. If they look the same, *whoosh* — one crumples and tossed into a bin marked `0.92 similarity → discard`. If different (a new slide), *snap!* — frame is pinned to a corkboard. The corkboard fills with ~6 distinct slides.
**Bubble (Lens, once):** *"Same slide. Skip."*
**Label:** `Lens — Keyframe extractor · SSIM dedup`
**VO:** "Visually, only frames that *change* are kept — duplicate slides are dropped, so the index stays small and the answers stay focused."

### Scene 4 — Indie files everything in the library  (0:30 – 0:48)
**Visual:** Camera pans right. A wall of tiny drawers — the **Vector Library**. Indie takes each transcript strip and each pinned frame, holds it up; a coordinate vector `[0.12, –0.44, 0.81, …]` floats out and the item slides itself into a drawer at that location. Text strips and frame photos go into the *same* library — visualized as both landing in nearby drawers.
**Bubble (Indie):** *"Same space. Text and pixels."*
**Label:** `Indie — Chroma + Jina CLIP v2 (text + image, 1024-dim)`
**VO:** "Both text and frames are embedded into the *same* vector space — so a question can find a slide image as easily as a transcript line."

### Scene 5 — Lights up  (0:48 – 0:55)
**Visual:** Sign flips from "Closed" to **"Now Serving."** Maitre walks in, ties apron. Camera holds for a beat.
**VO:** "By the time you ask, the kitchen is already prepped."

---

## ACT II — *Service*  (~1:35)
*Goal: follow one ticket from order → answer, end-to-end. This is the heart of the video.*

### Scene 6 — The customer pauses  (0:55 – 1:08)
**Visual:** Customer at the dining table, screen showing a YouTube lecture (3Blue1Brown-style neural-net frame). Lecture pauses at **04:32** (timestamp readout visible). Customer scratches head. Types into a notepad: **"Why does the gradient point uphill?"** A small printer on the table *chk-chk-chk* prints **the order ticket**.
**VO:** "You pause at minute four, thirty-two. You ask the only question you actually have."
**On-screen ticket reads:**
```
Q:  Why does the gradient point uphill?
t = 04:32
video: 3OmfTIf-SOU
```

### Scene 7 — Maitre routes the ticket  (1:08 – 1:18)
**Visual:** Maitre snatches the ticket, hustles. Camera follows the ticket through the dining room, past the pantry, into the library. A faint route line traces behind. Brief on-screen tag: `POST /api/ask`.
**Bubble (Maitre):** *"Order in!"*
**Label:** `Maitre — FastAPI · backend/app.py`
**VO:** "The request is routed through the API layer. No model work happens here — just transport."

### Scene 8 — Indie embeds + retrieves  (1:18 – 1:40)
**Visual:** Indie reads the ticket aloud silently. The question text on the ticket lifts off as glowing letters, condenses into a glowing arrow with a coordinate label `[0.31, –0.07, …]`. Indie walks the arrow into the library, stops at one drawer, slides it open: **a tray of 10 transcript scrolls + 3 photos** rises out, glowing with similarity scores.
**Bubble (Indie):** *"Top 10. Plus three frames."*
**VO:** "The question is embedded into the same space as the lecture. The ten nearest transcript chunks — and three nearest slides — come up together."

### Scene 9 — Timestamp re-rank  (1:40 – 1:52)
**Visual:** Indie sets the tray on a small turntable. The turntable spins and **reshuffles** the items — the ones with timestamps near `04:32` rise to the top, items from far away (eg. `21:15`) sink to the bottom. A subtle bar appears: distance from 04:32.
**Bubble (Indie):** *"Closer in time, closer to the top."*
**VO:** "Then we re-rank by *when* — chunks near the moment you asked are weighted higher. Locality matters."

### Scene 10 — The fresh catch (live frame)  (1:52 – 2:05)
**Visual:** Maitre detours past a frosted-glass **freezer door** labeled `cached .mp4`. Opens it — frosty mist. Reaches in and pulls out a single **photo card stamped `t = 04:32 (exact)`**. Adds it to the front of the tray. Tray now: digest card + 10 scrolls + 1 *exact* live frame + 3 keyframes.
**Bubble (Maitre):** *"Fresh, at 04:32."*
**Label:** `live_frame.py — exact-second capture from cached video`
**VO:** "And the *exact* frame at the moment you paused is grabbed live — even if it wasn't stored as a keyframe. The model sees what *you* saw."

### Scene 11 — Chef Vee cooks  (2:05 – 2:30)
**Visual:** Tray arrives at the kitchen counter. Chef Vee dons a pair of **glasses with two lenses** — one shaped like a `T` (text), one like a tiny picture frame (vision). Spreads the ingredients out. Looks at one scroll, then one photo, then back. A wok lights up. Words begin **plating themselves** onto a white dish, one phrase at a time. Each citation lands as a small **gold tag** `[04:30]`, `[04:35]`, `[05:02]` — garnishes around the rim.
**Bubble (Vee):** *"Reading text. And pixels."*
**Label:** `Chef Vee — Groq Llama-4 Scout (vision-language)`
**VO:** "A vision-language model assembles the answer — using the transcript chunks *and* the slides as evidence. Every claim is plated next to the timestamp it came from."
**On-dish text (renders progressively):**
> *"The gradient points in the direction of steepest **ascent** — uphill on the loss surface [04:30]. We negate it for descent [04:35]. The slide at 5:02 shows this as the arrow opposite to the contour normal [05:02]."*

### Scene 12 — Critic tastes  (2:30 – 2:42)
**Visual:** Critic walks in with a clipboard. Takes a small bite. Three **stamps** thump down on the dish edge:
- **Clarity 5/5**
- **ECT 4/5** *(Educational Content Tone)*
- **UPT 5/5** *(User-Perceived Trust)*
**Bubble (Critic):** *"Cited. Grounded. Approved."*
**Label:** `Critic — Llama 3.3 70B · LLM-as-judge`
**VO:** "A second model grades the answer on clarity, tone, and trustworthiness — so you can see, at a glance, how confident this dish is."

### Scene 13 — Delivery + click-through  (2:42 – 3:00)
**Visual:** Maitre carries the plated answer back to the table. **The order ticket is stapled to the side of the plate** — same `t = 04:32`, same question — closing the loop. Customer reads, taps the **[04:30]** garnish on the plate. The YouTube screen on the table **jumps to 04:30** — the lecture frame matches what Vee plated. Customer's eyes go wide.
**Bubble (Customer):** *"Wait — that's the exact moment."*
**VO:** "Tap a citation. The lecture jumps to that exact second. Every answer is traceable to a moment you can re-watch."

---

## ACT III — *Two Doors*  (~25 s)
*Goal: USP scene — concise, devastating.*

### Scene 14 — Pull back to the street  (3:00 – 3:25)
**Visual:** Camera pulls back: two doorways side-by-side on the same dark street.
- **Left door:** sign reads **"Generic Diner."** Through it: a chef cooks from a giant tome labeled **`Internet ∪ Books`**. Plates a beige answer. Customer asks: *"…but where in **my** lecture?"* Chef shrugs.
- **Right door:** sign reads **"EduVidQA Kitchen."** Same customer, same question. Plate arrives with **gold [mm:ss] garnishes**, each linked back to the lecture frame floating above the table.
**VO (over both):** "Generic chatbots cook from everything. We cook from *your* lecture — and we tell you exactly where each ingredient came from."
**On-screen tagline (lands on cut to right door):**
> **Every answer is traceable to a moment in the lecture.**

---

## ACT IV — *CTA*  (~15 s)
### Scene 15 — Curtain call  (3:25 – 3:40)
**Visual:** All six characters line up in front of the restaurant — Maitre, Quill, Lens, Indie, Vee, Critic — small wave. Sign above: **"EduVidQA."** URL appears beneath: `eduvidqa.app` (placeholder).
**Bubble (Maitre):** *"Bring a lecture."*
**VO:** "Paste any YouTube lecture. Ask anything. We'll show you where the answer lives."

---

## Production notes for the Manim build (just so we're aligned before I write code)

1. **Single `RestaurantFloorplan` VGroup** holding pantry/library/kitchen/table positions. Camera moves across it; we *never* `Clear()` between scenes.
2. **`PiChef` helper class** — parameterized pi-creature (color, prop, expression). Six instances. ~40 LOC total.
3. **`OrderTicket` Mobject** — single instance, animated through every Act II scene. Continuity prop.
4. **`SpeechBubble(text, anchor)`** — 3-line max, auto-positions, fades in/out in <0.4s. Hard rule: never two bubbles on screen at once.
5. **No `FadeIn` on whole scenes.** Transitions = camera moves + a character crossing the frame edge.
6. **Lower-third labels** appear on character's *first* entrance only, hold 2 s, slide out. Tech credibility without clutter.
7. **VO timing assumed at ~150 wpm.** I'll mark `self.wait()` durations in the code to match the script above.
8. **Render target:** 720p30 first for review. 1080p60 only after script is locked.

---

## What I need from you before I write code

1. **Verdict on the script.** Any scene that bores you, cut now. Any line of VO that sounds wrong, fix now. Cheaper here than after rendering.
2. **VO source.** Will *you* record the narration, or do we want on-screen text only (no voice)? If on-screen only, I'll widen the camera holds and shorten the VO lines to caption-length.
3. **Visual register confirmation.** Confirm: dark 3b1b background + soft-pastel pi-characters. (Alternative: warm beige "storybook" — but I'd argue against it for a research/edtech audience.)
4. **Tagline check.** Keeping "Every answer is traceable to a moment in the lecture." — yes/no?
5. **End-card URL.** Real domain or `eduvidqa.app` placeholder?

Once you sign off (even partially) I'll write `scripts/explainer_v4.py` end-to-end.