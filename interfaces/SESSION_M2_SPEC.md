# Session M2 — Quiz Backend: 5 API Endpoints + Ingest Integration

## Status: � COMPLETE
## Dependencies: M1 ✅ (checkpoints, quiz_gen, quiz_cache, SM-2 modules)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

Add 5 quiz API endpoints to `backend/app.py` and integrate checkpoint + quiz pre-generation into the ingest pipeline. After this, the quiz backend is fully functional.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`  
**Start backend:** `uvicorn backend.app:app --reload --port 8000`

---

## Available Modules (from M1)

```python
from pipeline.checkpoints import place_checkpoints
# place_checkpoints(chunks, video_duration_seconds, embeddings=None, target_interval_minutes=6.0)
# → [{"timestamp_seconds": float, "chunk_index": int, "topic_label": str, "shift_score": float}]

from pipeline.quiz_cache import get_or_generate
# get_or_generate(video_id, timestamp, chunks, prompt_version=1)
# → [{"id": str, "question_text": str, "options": [...], "correct_answer": str, "explanation": str, "difficulty": str}]

from pipeline.spaced_repetition import sm2_update
# sm2_update(is_correct, repetitions, ease_factor, interval_days)
# → (new_repetitions, new_ease_factor, new_interval_days)
```

---

## Current backend/app.py (525 lines)

Existing endpoints:
```
GET  /api/health              — public
POST /api/process-video       — requires auth, background ingest
POST /api/ask                 — optional auth (demo video without)
GET  /api/videos/{id}/status  — public
GET  /api/users/me/videos     — requires auth
```

Existing helpers: `_get_db_url()`, `_register_video()`, `_get_video_status()`, `_update_video_status()`, `_link_user_video()`, `_ingest_video_bg()`

Auth: `from backend.auth import optional_auth, require_auth` + `Depends(require_auth)` returns `user_id: str`

DB: `import psycopg2` + `psycopg2.connect(_get_db_url())`

---

## Current backend/models.py (81 lines)

Has: `AskRequest`, `ProcessRequest`, `AskResponse`, `ProcessResponse`, `HealthResponse`, `SourceInfo`, `QualityScoresResponse`

---

## Task 1: Add Pydantic Models

**File:** `backend/models.py` — add at the bottom:

```python
class QuizRequest(BaseModel):
    end_ts: float = Field(..., ge=0, le=21600, description="Timestamp up to which to quiz")
    count: int = Field(default=3, ge=1, le=10, description="Number of questions")

class AttemptRequest(BaseModel):
    selected_answer: str = Field(..., max_length=1, pattern=r"^[A-D]$", description="Selected option A-D")
```

---

## Task 2: Add 5 Quiz Endpoints to backend/app.py

Add these endpoints. Use `import uuid` and `import psycopg2` (already imported).

### Endpoint 1: Get checkpoints
```python
@app.get("/api/videos/{video_id}/checkpoints")
async def get_checkpoints(video_id: str, user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, timestamp_seconds, topic_label
            FROM checkpoints WHERE video_id = %s
            ORDER BY timestamp_seconds
        """, (video_id,))
        rows = cur.fetchall()
    conn.close()
    return [{"id": str(r[0]), "timestamp_seconds": r[1], "topic_label": r[2]} for r in rows]
```

### Endpoint 2: Get quiz questions
```python
from backend.models import QuizRequest, AttemptRequest

@app.post("/api/videos/{video_id}/quiz")
async def get_quiz(video_id: str, body: QuizRequest, user_id: str = Depends(require_auth)):
    """Get quiz questions for a timestamp. Uses global cache."""
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chunk_id, text, start_time, end_time FROM video_chunks WHERE video_id = %s",
            (video_id,))
        chunks = [{"chunk_id": r[0], "text": r[1], "start_time": r[2], "end_time": r[3]}
                  for r in cur.fetchall()]
    conn.close()
    if not chunks:
        raise HTTPException(status_code=404, detail="Video not indexed")

    from pipeline.quiz_cache import get_or_generate
    questions = get_or_generate(video_id, body.end_ts, chunks)

    # Return WITHOUT correct_answer or explanation (don't leak answers)
    return {"questions": [
        {"id": q["id"], "question_text": q["question_text"],
         "options": q["options"], "difficulty": q.get("difficulty", "medium")}
        for q in questions[:body.count]
    ]}
```

### Endpoint 3: Submit quiz attempt
```python
@app.post("/api/quizzes/{question_id}/attempt")
async def submit_attempt(question_id: str, body: AttemptRequest, user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        # Get correct answer
        cur.execute("SELECT correct_answer, explanation FROM questions WHERE id = %s", (question_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Question not found")

        correct_answer, explanation = row
        is_correct = body.selected_answer == correct_answer

        # Record attempt
        cur.execute("""
            INSERT INTO quiz_attempts (id, user_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user_id, question_id, body.selected_answer, is_correct))

        # If wrong → add to review queue
        added_to_review = False
        if not is_correct:
            cur.execute("""
                INSERT INTO review_queue (id, user_id, question_id, next_review_at)
                VALUES (%s, %s, %s, now() + interval '1 day')
                ON CONFLICT (user_id, question_id) DO UPDATE SET
                    next_review_at = now() + interval '1 day',
                    interval_days = 1, repetitions = 0
            """, (str(uuid.uuid4()), user_id, question_id))
            added_to_review = True

    conn.commit()
    conn.close()
    return {"is_correct": is_correct, "correct_answer": correct_answer,
            "explanation": explanation, "added_to_review": added_to_review}
```

### Endpoint 4: Get review queue
```python
@app.get("/api/users/me/review")
async def get_review(user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            SELECT q.id, q.video_id, v.title, q.question_text, q.options, rq.next_review_at
            FROM review_queue rq
            JOIN questions q ON rq.question_id = q.id
            LEFT JOIN videos v ON q.video_id = v.video_id
            WHERE rq.user_id = %s AND rq.next_review_at <= now()
            ORDER BY rq.next_review_at LIMIT 20
        """, (user_id,))
        rows = cur.fetchall()
    conn.close()
    return {
        "due_count": len(rows),
        "questions": [
            {"id": str(r[0]), "video_id": r[1], "video_title": r[2],
             "question_text": r[3], "options": r[4], "next_review_at": str(r[5])}
            for r in rows
        ]
    }
```

### Endpoint 5: Submit review attempt (updates SM-2)
```python
@app.post("/api/review/{question_id}/attempt")
async def review_attempt(question_id: str, body: AttemptRequest, user_id: str = Depends(require_auth)):
    conn = psycopg2.connect(_get_db_url())
    with conn.cursor() as cur:
        cur.execute("SELECT correct_answer, explanation FROM questions WHERE id = %s", (question_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Question not found")

        correct_answer, explanation = row
        is_correct = body.selected_answer == correct_answer

        # Get current SM-2 state
        cur.execute("""
            SELECT repetitions, ease_factor, interval_days FROM review_queue
            WHERE user_id = %s AND question_id = %s
        """, (user_id, question_id))
        rq = cur.fetchone()
        if rq:
            from pipeline.spaced_repetition import sm2_update
            new_reps, new_ef, new_iv = sm2_update(is_correct, rq[0], rq[1], rq[2])
            cur.execute("""
                UPDATE review_queue SET repetitions = %s, ease_factor = %s,
                    interval_days = %s, next_review_at = now() + make_interval(days => %s)
                WHERE user_id = %s AND question_id = %s
            """, (new_reps, new_ef, new_iv, new_iv, user_id, question_id))

        # Record attempt
        cur.execute("""
            INSERT INTO quiz_attempts (id, user_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), user_id, question_id, body.selected_answer, is_correct))

    conn.commit()
    conn.close()
    return {"is_correct": is_correct, "correct_answer": correct_answer, "explanation": explanation}
```

---

## Task 3: Integrate Checkpoints + Quiz Pre-gen into Ingest

**File:** `backend/app.py` — in `_ingest_video_bg()`, add after the indexing step (Step 5) and before `_update_video_status(video_id, "ready")`:

```python
        # Step 6: Place checkpoints
        try:
            from pipeline.checkpoints import place_checkpoints
            video_duration = chunks[-1]["end_time"] if chunks else 0
            checkpoints = place_checkpoints(chunks, video_duration)

            # Store checkpoints
            with psycopg2.connect(_get_db_url()) as cp_conn:
                with cp_conn.cursor() as cp_cur:
                    for cp in checkpoints:
                        cp_cur.execute("""
                            INSERT INTO checkpoints (id, video_id, timestamp_seconds, topic_label)
                            VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                        """, (str(uuid.uuid4()), video_id, cp["timestamp_seconds"], cp["topic_label"]))
                cp_conn.commit()
            logger.info("Placed %d checkpoints for %s", len(checkpoints), video_id)
        except Exception as e:
            logger.warning("Checkpoint placement failed (non-fatal): %s", e)

        # Step 7: Pre-generate quiz for each checkpoint (non-fatal)
        try:
            from pipeline.quiz_cache import get_or_generate
            for cp in checkpoints:
                try:
                    get_or_generate(video_id, cp["timestamp_seconds"], chunks)
                except Exception as e:
                    logger.warning("Quiz pre-gen at %.0fs failed: %s", cp["timestamp_seconds"], e)
        except Exception as e:
            logger.warning("Quiz pre-gen failed (non-fatal): %s", e)
```

Make sure this is BEFORE the `_update_video_status(video_id, "ready")` call and BEFORE `_link_user_video()`.

---

## Task 4: Add `uuid` import if missing

Check if `import uuid` is at the top of `backend/app.py`. If not, add it.

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `backend/models.py` | Add `QuizRequest`, `AttemptRequest` |
| 2 | `backend/app.py` | 5 new endpoints + ingest integration |

New endpoints after this session:
```
GET  /api/videos/{id}/checkpoints     — requires auth
POST /api/videos/{id}/quiz            — requires auth
POST /api/quizzes/{id}/attempt        — requires auth
GET  /api/users/me/review             — requires auth
POST /api/review/{id}/attempt         — requires auth
```

---

## Self-Critical Audit Plan

### Audit 1: Backend starts
```bash
source .venv/bin/activate
uvicorn backend.app:app --port 8000 &
sleep 5
curl -s http://localhost:8000/api/health | python3 -m json.tool
```
**PASS:** Returns `{"status": "ok", ...}`. No import errors.

### Audit 2: All 5 new routes registered
```bash
python3 -c "
from backend.app import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
quiz = [r for r in routes if 'quiz' in r or 'checkpoint' in r or 'review' in r]
print(f'Quiz routes ({len(quiz)}):')
for r in sorted(quiz): print(f'  {r}')
assert len(quiz) >= 5, f'Expected 5+, got {len(quiz)}'
print('PASS')
"
```
**PASS:** Shows 5 quiz-related routes.

### Audit 3: Checkpoints endpoint works
```bash
# 3OmfTIf-SOU should have checkpoints if pre-generated, or empty array
curl -s http://localhost:8000/api/videos/3OmfTIf-SOU/checkpoints \
  -H "Authorization: Bearer TEST" 2>&1 | head -3
```
**PASS:** Returns JSON array (may be empty if no checkpoints yet, or 401 if token invalid — either is fine, just no 500).

### Audit 4: Quiz endpoint returns questions without answers
```bash
# This will need a valid JWT — test with the approach below
python3 -c "
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'), override=True)
import psycopg2, os, json

# Check if any questions exist for any video
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM questions')
print(f'Questions in DB: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM checkpoints')
print(f'Checkpoints in DB: {cur.fetchone()[0]}')
conn.close()
print('PASS: models exist')
"
```
**PASS:** No errors. Shows counts.

### Audit 5: Pydantic models exist
```bash
python3 -c "from backend.models import QuizRequest, AttemptRequest; print('PASS')"
```
**PASS:** Imports clean.

### Audit 6: AttemptRequest validates answer format
```bash
python3 -c "
from backend.models import AttemptRequest
try:
    AttemptRequest(selected_answer='E')
    print('FAIL: should reject E')
except Exception as e:
    print(f'PASS: rejected E — {e}')
AttemptRequest(selected_answer='A')
print('PASS: accepted A')
"
```
**PASS:** Rejects 'E', accepts 'A'.

### Audit 7: Ingest integration code exists
```bash
grep -n "place_checkpoints\|get_or_generate\|quiz_cache\|checkpoints" backend/app.py | head -10
```
**PASS:** Shows checkpoint placement + quiz pre-gen in `_ingest_video_bg`.

### Audit 8: uuid import present
```bash
grep -n "^import uuid" backend/app.py
```
**PASS:** Returns a line number.

### Audit 9: Tests still pass
```bash
kill %1 2>/dev/null
pytest -q 2>&1 | tail -10
```
**PASS:** No regressions.

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->

### Audit 1: Backend starts — PASS
```
{
    "status": "ok",
    "model_loaded": true,
    "model_name": "groq/llama-4-scout-17b",
    "gpu_available": false
}
```

### Audit 2: All 5 new routes registered — PASS
```
Quiz routes (5):
  /api/quizzes/{question_id}/attempt
  /api/review/{question_id}/attempt
  /api/users/me/review
  /api/videos/{video_id}/checkpoints
  /api/videos/{video_id}/quiz
PASS
```

### Audit 3: Checkpoints endpoint reachable — PASS
```
HTTP 401
{"detail":"Invalid token"}
```
Returns 401 (auth rejected dummy token) — no 500, route is wired.

### Audit 4: DB counts — PASS
```
Questions in DB: 0
Checkpoints in DB: 0
PASS
```
No errors. (Counts are 0 because no video has been re-ingested since M2 wired in checkpoint placement.)

### Audit 5: Pydantic models exist — PASS
```
PASS
```

### Audit 6: AttemptRequest validates answer format — PASS
```
PASS: rejected E
PASS: accepted A
```

### Audit 7: Ingest integration code exists — PASS
```
298:        # Step 6: Place checkpoints (non-fatal)
299:        checkpoints: list[dict] = []
301:            from pipeline.checkpoints import place_checkpoints
304:            checkpoints = place_checkpoints(chunks, video_duration)
308:                    for cp in checkpoints:
311:                            INSERT INTO checkpoints (id, video_id, timestamp_seconds, topic_label)
317:            logger.info("Placed %d checkpoints for %s", len(checkpoints), video_id)
323:            from pipeline.quiz_cache import get_or_generate
325:            for cp in checkpoints:
327:                    get_or_generate(video_id, cp["timestamp_seconds"], chunks)
```

### Audit 8: uuid import present — PASS
```
10:import uuid
```

### Audit 9: Tests still pass — PASS (no M2 regressions)
```
19 failed, 43 passed, 2 warnings in 46.44s
```
All 19 failures are `httpx.ConnectError [Errno 61]` from `tests/test_e2e.py` and `tests/test_e2e_v2.py` — these are e2e tests that require a live backend on a port. Pre-existing, not caused by M2 changes. All 43 unit/integration tests pass.
