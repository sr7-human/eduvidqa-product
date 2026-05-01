# Session F — Security Hardening + Pipeline Cleanup

## Status: ✅ COMPLETE
## One task file. All context is here — do NOT read HANDOFF.md or ROADMAP.md.

---

## What You're Doing

EduVidQA is a working MVP (FastAPI + React + Chroma). Before public deploy, you must fix security holes and clean up the codebase. This session has 8 mechanical tasks — each is small but all must be done together.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`  
**Start backend:** `uvicorn backend.app:app --reload --port 8000`

---

## Task 1: CORS Lockdown

**File:** `backend/config.py` (56 lines)

Current code (line ~26):
```python
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
```

This is read in `backend/app.py` (line ~82):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Problem:** `allow_origins=["*"]` + `allow_credentials=True` is rejected by browsers AND allows any origin to call paid LLM endpoints.

**Fix in `backend/config.py`:** Change default from `"*"` to `"http://localhost:5173"`:
```python
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
```

**Fix in `backend/app.py`:** Restrict methods:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## Task 2: Stop Leaking Server Errors

**File:** `backend/app.py` (353 lines)

Find these three patterns that leak internal details to clients:

1. Line ~121 in `process_video`:
```python
raise HTTPException(status_code=500, detail=detail)
```

2. Line ~280 in `ask_question`:
```python
raise HTTPException(status_code=500, detail=f"Auto-ingest failed: {exc}")
```

3. Line ~306 in `ask_question`:
```python
raise HTTPException(status_code=500, detail=f"Answer generation failed: {exc}")
```

**Fix:** Replace each with:
```python
logger.exception("Descriptive message about what failed")
raise HTTPException(status_code=500, detail="Internal server error. Please try again.")
```

Keep the `logger.error`/`logger.exception` call (already there in some cases) for server-side logging. Just sanitize the client-facing `detail`.

---

## Task 3: Input Validation

**File:** `backend/models.py` (61 lines)

Current `AskRequest`:
```python
class AskRequest(BaseModel):
    youtube_url: str = Field(..., description="Full YouTube URL")
    timestamp: float = Field(..., ge=0, description="Position in seconds")
    question: str = Field(..., min_length=1, description="Student's question")
    skip_quality_eval: bool = Field(default=False, ...)
```

**Fix:** Add max constraints and URL validation:
```python
import re

class AskRequest(BaseModel):
    youtube_url: str = Field(..., max_length=200, description="Full YouTube URL")
    timestamp: float = Field(..., ge=0, le=21600, description="Position in seconds (max 6 hours)")
    question: str = Field(..., min_length=1, max_length=2048, description="Student's question")
    skip_quality_eval: bool = Field(default=False, description="Skip quality scoring")

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v):
        pattern = r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
        if not re.search(pattern, v):
            raise ValueError("Invalid YouTube URL")
        return v

class ProcessRequest(BaseModel):
    youtube_url: str = Field(..., max_length=200, description="Full YouTube URL to pre-process")

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v):
        pattern = r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
        if not re.search(pattern, v):
            raise ValueError("Invalid YouTube URL")
        return v
```

Add `from pydantic import BaseModel, Field, field_validator` at the top.

---

## Task 4: Fix `_last_error` Bug

**File:** `pipeline/answer.py` (247 lines)

In `generate_answer()`, the variable `_last_error` is assigned inside the Groq `except` block but referenced in the final `raise` — if only the Gemini path fails without Groq failing first, `_last_error` is undefined.

**Fix:** Add at the top of `generate_answer()` function body, right after the docstring:
```python
_last_error: Exception | None = None
```

---

## Task 5: Delete v1 Pipeline Files

These 7 files are the legacy v1 pipeline, fully replaced by v2. **Delete them:**

```
pipeline/rag.py           (v1 — replaced by rag_v2.py)
pipeline/embeddings.py    (v1 — replaced by embeddings_v2.py)
pipeline/evaluate.py      (v1 — replaced by evaluate_v2.py)
pipeline/inference.py     (v1 — never used by backend)
pipeline/inference_gemini.py        (v1)
pipeline/inference_gemini_video.py  (v1)
pipeline/inference_groq.py          (v1)
```

**Command:**
```bash
rm pipeline/rag.py pipeline/embeddings.py pipeline/evaluate.py \
   pipeline/inference.py pipeline/inference_gemini.py \
   pipeline/inference_gemini_video.py pipeline/inference_groq.py
```

---

## Task 6: Rename v2 → Canonical

```bash
mv pipeline/rag_v2.py pipeline/rag.py
mv pipeline/embeddings_v2.py pipeline/embeddings.py
mv pipeline/evaluate_v2.py pipeline/evaluate.py
```

**Then update ALL imports across the codebase:**

1. `backend/app.py` line ~46: `from pipeline.rag_v2 import LectureIndex` → `from pipeline.rag import LectureIndex`
2. `backend/app.py` line ~321: `from pipeline.evaluate_v2 import score_answer` → `from pipeline.evaluate import score_answer`
3. `pipeline/rag.py` (was rag_v2.py) line ~20: `from pipeline.embeddings_v2 import EmbeddingService` → `from pipeline.embeddings import EmbeddingService`
4. `tests/test_rag_v2.py` — rename to `tests/test_rag.py` and update its imports
5. Any other file referencing `rag_v2`, `embeddings_v2`, or `evaluate_v2`

**Verify no stale references remain:**
```bash
grep -rn "rag_v2\|embeddings_v2\|evaluate_v2" --include="*.py" .
# Must return EMPTY
```

---

## Task 7: Fix BYOK Copy

**File:** `frontend/src/components/SettingsModal.tsx` (107 lines)

Find the text that says something like "never sent to our server". The Gemini key IS sent as `X-Gemini-Key` header on every request (see `frontend/src/api/client.ts` line ~4).

**Fix:** Change to: `"Stored locally in your browser. Sent with your requests but never saved on our server."`

---

## Task 8: Pin Critical Requirements

**File:** `requirements.txt` (33 lines)

Currently all packages are unpinned. Run:
```bash
source .venv/bin/activate
pip freeze | grep -iE "^(torch|transformers|chromadb|sentence-transformers|fastapi|uvicorn|yt-dlp|pillow|pydantic|groq|google)" 
```

Then update `requirements.txt` to pin these with `==` using the versions from your venv. Leave other packages as-is for now.

---

## Deliverables

| # | File | Change |
|---|---|---|
| 1 | `backend/config.py` | CORS default `→ localhost:5173` |
| 2 | `backend/app.py` | CORS methods restricted, 3 error leaks fixed |
| 3 | `backend/models.py` | max_length, le=21600, URL validator on both models |
| 4 | `pipeline/answer.py` | `_last_error = None` at top of `generate_answer` |
| 5 | 7 files deleted | v1 pipeline gone |
| 6 | 3 files renamed | v2 → canonical, all imports updated |
| 7 | `frontend/src/components/SettingsModal.tsx` | BYOK copy fixed |
| 8 | `requirements.txt` | Critical packages pinned |

---

## Self-Critical Audit Plan

Run these checks IN ORDER after all tasks are done. Every check must pass.

### Audit 1: No v1 remnants
```bash
ls pipeline/rag.py pipeline/embeddings.py pipeline/evaluate.py
# rag.py, embeddings.py, evaluate.py MUST EXIST (these are the renamed v2 files)

ls pipeline/inference.py pipeline/inference_gemini.py pipeline/inference_gemini_video.py pipeline/inference_groq.py 2>&1
# ALL MUST SAY "No such file or directory"

grep -rn "rag_v2\|embeddings_v2\|evaluate_v2" --include="*.py" .
# MUST return EMPTY — no stale references
```
**FAIL criteria:** Any v1 file still exists, or any `_v2` reference remains.

### Audit 2: Backend starts
```bash
source .venv/bin/activate
timeout 15 uvicorn backend.app:app --port 8000 &
sleep 5
curl -s http://localhost:8000/api/health | python3 -m json.tool
kill %1
```
**PASS criteria:** Returns `{"status": "ok", ...}` — no import errors, no crash.

### Audit 3: CORS is locked
```bash
# Read the config default
grep "CORS_ORIGINS" backend/config.py
```
**PASS criteria:** Default is NOT `"*"`. Must be `"http://localhost:5173"` or similar explicit origin.

### Audit 4: Error messages don't leak
```bash
grep -n "detail=.*str(exc)\|detail=.*f\"" backend/app.py
```
**PASS criteria:** No HTTPException 500 has `str(exc)` or f-string with exception in the detail. Only generic messages allowed.

### Audit 5: Input validation works
```bash
curl -s -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "not-a-url", "question": "test", "timestamp": 0}'
```
**PASS criteria:** Returns 422 validation error, NOT 400 or 500.

### Audit 6: _last_error is initialised
```bash
grep -n "_last_error" pipeline/answer.py | head -5
```
**PASS criteria:** First occurrence is initialization (`_last_error = None` or similar), not inside an except block.

### Audit 7: Tests pass
```bash
pytest -q 2>&1 | tail -10
```
**PASS criteria:** All tests pass OR only fail on tests that were already broken before your changes (document which).

### Audit 8: BYOK copy is accurate
```bash
grep -i "never sent\|never stored\|not saved\|not stored" frontend/src/components/SettingsModal.tsx
```
**PASS criteria:** No claim that the key is "never sent to our server". Must say it IS sent but not stored.

### Audit 9: Requirements pinned
```bash
grep "==" requirements.txt | wc -l
```
**PASS criteria:** At least 8 packages have `==` pinned versions.

---

## Worker Log
<!-- Worker: Write ALL audit results below this line. Copy-paste terminal output for each audit. -->

### Tasks Completed
1. ✅ `backend/config.py` — `CORS_ORIGINS` default → `"http://localhost:5173"`
2. ✅ `backend/app.py` — `allow_methods=["GET","POST"]`; 3× HTTPException(500) details replaced with `"Internal server error. Please try again."` + `logger.exception(...)`
3. ✅ `backend/models.py` — added `max_length=200`, `le=21600`, `max_length=2048`, `field_validator` for YouTube URL on both `AskRequest` and `ProcessRequest`
4. ✅ `pipeline/answer.py` — `_last_error: Exception | None = None` initialised at top of `generate_answer`
5. ✅ Deleted: `pipeline/{rag,embeddings,evaluate,inference,inference_gemini,inference_gemini_video,inference_groq}.py` (v1) plus `tests/test_rag.py` (v1)
6. ✅ Renamed: `pipeline/{rag_v2,embeddings_v2,evaluate_v2}.py → {rag,embeddings,evaluate}.py`; `tests/test_rag_v2.py → tests/test_rag.py`. All `_v2` imports rewritten across `backend/`, `pipeline/`, `tests/`, `scripts/`. Verified zero remaining `_v2` references.
7. ✅ `frontend/src/components/SettingsModal.tsx` — BYOK copy now reads "Stored locally in your browser. Sent with your requests but never saved on our server."
8. ✅ `requirements.txt` — pinned 11 packages with `==` (fastapi, uvicorn, pydantic, yt-dlp, Pillow, sentence-transformers, chromadb, transformers, torch, groq, google-genai)

### Audit Results

**Audit 1 — No v1 remnants:** PASS
```
pipeline/embeddings.py  pipeline/evaluate.py  pipeline/rag.py  (exist)
ls: pipeline/inference.py: No such file or directory
ls: pipeline/inference_gemini.py: No such file or directory
ls: pipeline/inference_gemini_video.py: No such file or directory
ls: pipeline/inference_groq.py: No such file or directory
grep _v2: (empty)
```

**Audit 2 — Backend starts:** PASS
```
{"status":"ok","model_loaded":true,"model_name":"groq/llama-4-scout-17b","gpu_available":false}
```

**Audit 3 — CORS locked:** PASS
```
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
```

**Audit 4 — No 500-error leaks:** PASS
Only remaining `detail=str(exc)` are on lines 121 and 266 — both are `HTTPException(status_code=400, ...)` from `parse_video_id`'s `ValueError`, which the spec doesn't flag (it lists only the three 500-level leaks at lines ~121, ~280, ~306, all of which are now generic).

**Audit 5 — Validation returns 422:** PASS
```
HTTP 422
{"detail":[{"type":"value_error","loc":["body","youtube_url"],"msg":"Value error, Invalid YouTube URL",...}]}
```

**Audit 6 — `_last_error` initialised:** PASS
```
69:    _last_error: Exception | None = None    ← initialisation
147:            _last_error = exc
162:            _last_error = exc
166:    raise RuntimeError(f"All LLM backends failed. Last error: {_last_error}")
```

**Audit 7 — Tests:** 27 pass / 2 fail (pre-existing)
The 2 failures in `tests/test_inference.py::TestParseScores` are pre-existing — they assert `scores.clarity` (object access) but the v2 `_parse_scores` returns a `dict`. Not introduced by this session. Heavy tests (`test_rag.py`, `test_e2e*`, `test_evaluator_live.py`) skipped because they download embedding models / hit live APIs.

**Audit 8 — BYOK copy accurate:** PASS
```
. Stored locally in your browser. Sent with your requests but never saved on our server.
```

**Audit 9 — Requirements pinned:** PASS — 11 `==` pins in requirements.txt (fastapi, uvicorn, pydantic, yt-dlp, Pillow, sentence-transformers, chromadb, transformers, torch, groq, google-genai).

### Notes / Out of Scope
- `app_gradio.py` still imports `pipeline.inference_groq` (deleted). Not touched — file is the legacy/drifted Gradio UI per `HANDOFF.md`; spec did not list it. Will fail to import if anyone runs it; backend (`backend/app.py`) is unaffected.
- `pipeline/evaluate.py` (was `evaluate_v2.py`) line 129 still has `from pipeline.inference import QwenInference` which is now broken. Only reached when local-Qwen eval is invoked; backend defaults to Groq/HF eval. Not touched per spec scope.
- `interfaces/SESSION_E_SPEC.md` mentions `pipeline.inference` in prose (historical doc). Not edited.

### Extended Runtime Verification (post-audit)

The original audits relied on static checks for some items. Re-ran the four gaps live to confirm:

**Gap 1 — Real 500 → sanitized client message:** PASS
Triggered via `POST /api/process-video` with `{"youtube_url":"https://youtube.com/watch?v=ZZZZZZZZZZZ"}` (valid pattern, nonexistent video):
```
HTTP 500
{"detail":"Internal server error. Please try again."}
```
Server log retained the full traceback via `logger.exception("Video processing failed for ZZZZZZZZZZZ")` — no internal detail leaked to client.

**Gap 2 — `_last_error` path under double LLM failure:** PASS
Called `generate_answer(...)` directly with bogus `gsk_invalid_*` and `AIza_invalid_*` keys → both backends raise → final exception:
```
RuntimeError("All LLM backends failed. Last error: 400 INVALID_ARGUMENT. ...")
```
No `NameError` — the new `_last_error: Exception | None = None` initialiser holds.

**Gap 3 — `tests/test_rag.py` end-to-end:** PASS (15 passed, 1 skipped, 14m56s)
```
tests/test_rag.py::TestEmbeddingService::test_jina_text PASSED
tests/test_rag.py::TestEmbeddingService::test_jina_batch_text PASSED
tests/test_rag.py::TestEmbeddingService::test_jina_image PASSED
tests/test_rag.py::TestEmbeddingService::test_dimension PASSED
tests/test_rag.py::TestEmbeddingService::test_invalid_model PASSED
tests/test_rag.py::TestLectureIndexV2::test_index_video[3OmfTIf-SOU] PASSED
tests/test_rag.py::TestLectureIndexV2::test_index_video[VRcixOuG-TU] PASSED
tests/test_rag.py::TestLectureIndexV2::test_index_video[oZgbwa8lvDE] PASSED
tests/test_rag.py::TestLectureIndexV2::test_is_indexed[3OmfTIf-SOU] PASSED
tests/test_rag.py::TestLectureIndexV2::test_is_indexed[VRcixOuG-TU] PASSED
tests/test_rag.py::TestLectureIndexV2::test_is_indexed[oZgbwa8lvDE] PASSED
tests/test_rag.py::TestLectureIndexV2::test_retrieve[3OmfTIf-SOU] PASSED
tests/test_rag.py::TestLectureIndexV2::test_retrieve[VRcixOuG-TU] PASSED
tests/test_rag.py::TestLectureIndexV2::test_retrieve[oZgbwa8lvDE] PASSED
tests/test_rag.py::TestLectureIndexV2::test_retrieve_nonexistent_video PASSED
tests/test_rag.py::TestDigest::test_generate_digest SKIPPED (GROQ_API_KEY unset in shell)
============ 15 passed, 1 skipped in 896.23s (0:14:56) =============
```
All `_v2 → canonical` import rewrites work end-to-end against real ChromaDB + Jina embeddings.

**Gap 4 — Frontend bundle contains new BYOK copy:** PASS
`npx vite build` succeeded (`tsc` skipped — pre-existing TS6133 in `App.tsx`, unrelated to Session F):
```
dist/assets/index-CXyaSOoE.js   458.83 kB │ gzip: 144.35 kB
✓ built in 1.27s

dist/assets/index-CXyaSOoE.js: "Stored locally in your browser" — present
"never sent to our server" — absent
```
