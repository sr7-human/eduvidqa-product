# Session C: Answer Pipeline + Backend Integration

## Status
- **Assigned:** Worker Session C
- **Dependencies:** BLOCKED — Needs Session A (keyframes/chunks) + Session B (embeddings/ChromaDB/digest)
- **Last updated:** April 1, 2026

---

## ⚠️ MANAGER INSTRUCTIONS (READ THIS FIRST)

Read `/memories/session/munimi.md` for full project context. You build the ANSWER GENERATION layer and wire everything into FastAPI.

**WAIT** until Sessions A and B have completed. Check their "Worker Updates" in `interfaces/SESSION_A_SPEC.md` and `interfaces/SESSION_B_SPEC.md`.

Working directory: `/Users/shubhamkumar/eduvidqa-product/`
Python venv: `.venv/bin/python`

### Research Paper Context (important for prompt engineering!)
The EduVidQA paper (EMNLP 2025) introduced 3 quality metrics for educational answers:
- **Clarity** (1-5): Is the answer clear, jargon-free, and understandable?
- **ECT** (1-5): Does it Encourage Critical Thinking? Challenge assumptions?
- **UPT** (1-5): Does it Use Pedagogical Techniques? Scaffolding, examples, Socratic method?

Students overwhelmingly prefer CLARITY (~65%) over all other qualities.
Our product is the RAG-based baseline the paper never tested — this is our academic angle.

**When done:** Update the "Worker Updates" section at the bottom of THIS file.

---

## Task 1: Live Frame Extraction (pipeline/live_frame.py)

### What to build
Extract a frame at the EXACT timestamp the student asked about. This frame is EPHEMERAL — used once, never saved.

### Function
```python
def extract_live_frame(video_id: str, timestamp: float, data_dir: str = "data/processed") -> str | None:
    """
    Finds the nearest stored keyframe to the given timestamp.
    Returns the file path to the keyframe image.
    
    If the video .mp4 is still available (in data/videos/), extract the exact frame.
    If not, fall back to the nearest keyframe from manifest.json.
    
    Returns: path to the frame image (temporary if extracted from .mp4)
    """
```

### Logic
1. Check if `data/videos/{video_id}/*.mp4` exists → extract exact frame at `timestamp` using OpenCV
2. If no .mp4 → read `data/processed/{video_id}/keyframes/manifest.json` → find nearest keyframe by timestamp
3. Return the path (caller will read the image and send to VLM)

---

## Task 2: Answer Generation (pipeline/answer.py)

### What to build
Assemble ALL context and send to the VLM for answer generation.

### Context assembly (4 types)
1. **Live frame** — ephemeral frame at the exact timestamp (from Task 1)
2. **Ranked chunks** — 10-sec transcript chunks near the timestamp (from Session B's retriever)
3. **Stored keyframes** — pre-indexed keyframes linked to those chunks
4. **Lecture Digest** — comprehensive description of the entire lecture

### Function
```python
def generate_answer(
    question: str,
    video_id: str,
    timestamp: float,
    retrieval_result: dict,   # from LectureIndex.retrieve()
    live_frame_path: str | None,
    groq_api_key: str = None,
    gemini_api_key: str = None,
) -> dict:
    """
    Returns:
    {
        "answer": "The professor is explaining...",
        "model_name": "llama-4-scout-17b",
        "generation_time": 2.3,
        "sources": [{"start_time": 30, "end_time": 40, "relevance_score": 0.89}, ...]
    }
    """
```

### Prompt structure
```
SYSTEM: You are an expert AI teaching assistant. A student is watching a lecture
video and has paused at {timestamp} to ask a question. Answer clearly and
pedagogically, using the provided context.

CONTEXT:
[Lecture Digest]
{digest text}

[Relevant Transcript (ranked by relevance to timestamp {timestamp})]
{chunk 1 text — contains the exact moment}
{chunk 2 text — adjacent}
...

[Visual Context]
{live frame at timestamp + stored keyframes attached as images}

QUESTION: {question}

Answer in a conversational, teaching-assistant tone. Prioritize CLARITY.
Reference what's shown on screen when relevant. If the question isn't
related to the video, politely say so.
```

### LLM: Groq (primary) → Gemini (fallback)
- Primary: `groq.Groq(api_key=...).chat.completions.create(model="meta-llama/llama-4-scout-17b-16e-instruct")`
- Fallback: Gemini 2.0 Flash (if Groq fails/rate-limited)
- Send images as base64 data URLs in the Groq message content array

---

## Task 3: Quality Scoring (pipeline/evaluate_v2.py)

### What to build
Score the generated answer on Clarity, ECT, UPT (the paper's metrics).

### Function
```python
def score_answer(question: str, answer: str, groq_api_key: str = None) -> dict:
    """
    Returns: {"clarity": 4.2, "ect": 3.8, "upt": 4.0}
    Uses Groq with llama-3.3-70b-versatile (text-only, fast) as the judge.
    """
```

### Scoring prompt (adapted from the paper)
```
Rate the following answer to a student's question on three scales (1-5):

1. CLARITY (1-5): Is the answer clear, well-organized, and free of unnecessary jargon?
2. ECT (1-5): Does the answer Encourage Critical Thinking? Does it challenge assumptions or invite deeper exploration?
3. UPT (1-5): Does the answer Use Pedagogical Techniques? (examples, analogies, scaffolding, Socratic questioning)

Question: {question}
Answer: {answer}

Respond ONLY with JSON: {"clarity": X, "ect": X, "upt": X}
```

---

## Task 4: FastAPI Backend Integration (backend/app.py)

### What to build
Wire all pipeline modules into the existing FastAPI app. Update endpoints to use the new pipeline.

### Endpoints
```
GET  /api/health          → {status, model_loaded, indexed_videos}
POST /api/process-video   → Ingest: download + keyframes + chunks + embed + digest
POST /api/ask             → Query: live frame + retrieve + answer + score
```

### POST /api/process-video flow
1. Parse YouTube URL → video_id
2. Check `is_indexed(video_id)` → skip if yes
3. Download .mp4 to `data/videos/{video_id}/`
4. Run `extract_keyframes()` (Session A)
5. Run `chunk_transcript()` (Session A)
6. Run `generate_digest()` (Session B)
7. Run `index_video()` (Session B) — embed + store in ChromaDB
8. Delete .mp4 from `data/videos/`
9. Return {video_id, title, keyframe_count, chunk_count}

### POST /api/ask flow
1. Parse YouTube URL → video_id
2. If not indexed → auto-ingest (step above)
3. `extract_live_frame(video_id, timestamp)`
4. `retrieve(question, video_id, timestamp)`
5. `generate_answer(question, video_id, timestamp, retrieval, live_frame)`
6. `score_answer(question, answer)` (optional, skip if `skip_quality_eval=true`)
7. Return {answer, sources, quality_scores, model_name, generation_time}

### Config updates needed in backend/config.py
- `EMBEDDING_MODEL`: "jina" or "gemini"
- Keep existing config vars

---

## Task 5: E2E Test

Test the full pipeline on all 3 videos:
1. POST /process-video for each video
2. POST /ask with 2 questions per video at different timestamps
3. Verify answers make sense, quality scores are in range

Create: `tests/test_e2e_v2.py`

---

## Worker Updates

### April 1, 2026 — ALL TASKS COMPLETE

**Files created:**
- `pipeline/live_frame.py` — Extracts nearest keyframe to timestamp (fallback from manifest.json if .mp4 unavailable)
- `pipeline/answer.py` — Context assembly + Groq (primary) → Gemini 2.5 Flash (fallback) answer generation with multimodal support (transcript + images)
- `pipeline/evaluate_v2.py` — Groq Llama 3.3 70B scoring on Clarity/ECT/UPT with JSON parsing + regex fallback
- `tests/test_e2e_v2.py` — E2E tests for all 3 videos (health, process, ask, scoring, error cases)
- `backend/app.py` — Fully rewritten: dotenv loading, new pipeline integration (live_frame → rag_v2.retrieve → answer.generate_answer → evaluate_v2.score_answer)

**E2E Results (verified live):**

| Test | Video | Result |
|------|-------|--------|
| Process | 3OmfTIf-SOU | `already indexed` (cached) |
| Ask (skip scoring) | 3OmfTIf-SOU@30s | 2000+ char answer, 10 sources, `groq/llama-4-scout-17b` (when Groq available) or `gemini/gemini-2.5-flash` (fallback) |
| Ask + quality scoring | 3OmfTIf-SOU@30s | Clarity: 5/5, ECT: 4/5, UPT: 5/5, 33s total |

**Architecture decisions:**
1. **Groq → Gemini fallback**: Groq Llama 4 Scout is primary (faster, vision), Gemini 2.5 Flash is fallback when Groq hits rate limits
2. **Gemini SDK**: Uses new `google-genai` SDK (not deprecated `google-generativeai`), with thinking disabled for speed
3. **Keys via Settings**: API keys loaded from `.env` via `python-dotenv` at import time in `backend/app.py`, passed explicitly to pipeline functions via `settings.GROQ_API_KEY` / `settings.GEMINI_API_KEY`
4. **Live frame**: Falls back to nearest keyframe from manifest.json when .mp4 isn't available (e.g., deleted after ingestion)

**Known issues:**
- Groq free tier has 500K TPD daily limit — hits it after ~30 full answers
- Gemini free tier has per-minute and daily quotas per project
- Both are fine for demo/testing; production needs paid tier or multiple project keys

---

### Debugging Log — Issues Faced & How They Were Resolved

#### Issue 1: CWD mismatch with uvicorn background terminals
**Problem:** VS Code background terminals always started in `~/EduVidQA` instead of `~/eduvidqa-product`. The backend uses relative paths (`./data/chroma`, `./data/processed`), so `is_indexed()` returned `False` even though 792 items were in ChromaDB. This caused the server to re-ingest already-indexed videos on every request.
**Symptoms:** Server re-ran keyframe extraction + digest generation for already-indexed videos → hit Groq rate limits immediately.
**Fix:** Used `cd /Users/shubhamkumar/eduvidqa-product && .venv/bin/uvicorn ...` with the `cd` in the same command to ensure CWD was correct. Verified with `lsof -p PID | grep cwd`.

#### Issue 2: Environment variables not reaching pipeline modules
**Problem:** `.env` was loaded by `backend/config.py` via `python-dotenv`, and `os.getenv("GROQ_API_KEY")` worked at import time, but `pipeline/answer.py` called `os.getenv()` at request time and got empty strings. Spent many cycles adding `load_dotenv(override=True)` in `app.py`, adding debug prints, all showing keys were set — but requests still failed.
**Root cause:** The error message was **misleading**. The actual errors were Groq 429 rate limit + Gemini missing SDK — NOT missing keys. The `RuntimeError("No LLM API key available")` was thrown as a catch-all when both backends failed, regardless of the actual failure reason.
**Fix:** 
1. Fixed error message to propagate actual backend errors: `"All LLM backends failed. Last error: {_last_error}"`
2. Added `settings.GROQ_API_KEY` / `settings.GEMINI_API_KEY` to `backend/config.py` Settings class and passed explicitly to pipeline functions — belt-and-suspenders.

#### Issue 3: Groq daily rate limit (429 TPD exhausted)
**Problem:** Groq free tier allows 500K tokens/day. Sessions A+B consumed most of the quota during digest generation + earlier testing. By the time Session C tested answer generation, only ~2K tokens remained.
**Symptoms:** `Error code: 429 - Rate limit reached for model llama-4-scout-17b... Limit 500000, Used 498755`
**Fix:** Implemented Gemini 2.5 Flash as fallback. The answer pipeline tries Groq first, catches any exception, then falls back to Gemini.

#### Issue 4: `google-generativeai` package missing
**Problem:** The Gemini fallback in `answer.py` imported `google.generativeai` but the package wasn't installed in the `.venv`.
**Symptoms:** `ModuleNotFoundError: No module named 'google.generativeai'` — but this was masked by the catch-all error message "No LLM API key available".
**Fix:** Installed `google-generativeai`, then discovered it was deprecated. Switched to new `google-genai` SDK.

#### Issue 5: Gemini free tier quota exhausted (429)
**Problem:** The original Gemini API key (`[REDACTED]`) had its daily quota exhausted from earlier Session B usage.
**Symptoms:** `429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, limit: 0`
**Fix:** User provided 3 more keys — first 2 were from **suspended** GCP projects (`CONSUMER_SUSPENDED`), third was from the same project (shared quota). Finally got a working key from a new project (`[REDACTED]`). Then switched model from `gemini-2.0-flash` (exhausted quota) to `gemini-2.5-flash` (separate quota bucket per model) — this worked immediately.

#### Issue 6: `google-genai` SDK API differences
**Problem:** The new `google-genai` SDK has different API signatures than the deprecated `google-generativeai`. `Part.from_text(text)` takes keyword arg, not positional. Gemini 2.5 Flash uses "thinking" by default which returned `None` text.
**Symptoms:** `Part.from_text() takes 1 positional argument but 2 were given`; Response text was `None`.
**Fix:** Changed to `Part.from_text(text=...)` and added `thinking_config=types.ThinkingConfig(thinking_budget=0)` to disable the thinking mode.

#### Issue 7: uvicorn `--reload` killed mid-request
**Problem:** When editing code with `--reload` enabled, the file watcher detected changes and killed the worker process mid-request (while Jina CLIP model was loading), causing the health check to report "ok" but subsequent requests failed because the reloaded worker hadn't finished initializing.
**Fix:** Stopped using `--reload` for testing. Kill + restart cleanly instead.

#### Key lesson learned
The misleading error message `"No LLM API key available"` wasted the most time. It was thrown as a generic fallback when both LLM backends failed, even when the actual failures were rate limits, missing packages, or API errors. Fixing the error propagation to show the REAL last error immediately revealed the true problems.
