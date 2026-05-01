# Session M1 — Quiz Backend: Checkpoints + Question Gen + Caching + SM-2

## Status: 🟢 COMPLETE — all 6 audits PASS
## Dependencies: H1 ✅ (pgvector rag.py), I ✅ (auth + DB helpers)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

Build 4 new pipeline modules for the quiz feature: checkpoint placement, LLM question generation, global quiz caching, and SM-2 spaced repetition. **No API endpoints** — that's M2.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`  
**These files do NOT exist yet:** `pipeline/checkpoints.py`, `pipeline/quiz_gen.py`, `pipeline/quiz_cache.py`, `pipeline/spaced_repetition.py`

---

## DB Tables Already Exist (from Session G)

```sql
-- checkpoints: auto-placed markers on timeline
CREATE TABLE checkpoints (
    id UUID PRIMARY KEY, video_id VARCHAR(11) NOT NULL,
    timestamp_seconds FLOAT NOT NULL, topic_label TEXT,
    UNIQUE (video_id, timestamp_seconds)
);

-- questions: global cache (not per-user)
CREATE TABLE questions (
    id UUID PRIMARY KEY, video_id VARCHAR(11) NOT NULL,
    checkpoint_id UUID REFERENCES checkpoints(id),
    ts_bucket_30s INT NOT NULL,        -- floor(timestamp / 30)
    prompt_version INT DEFAULT 1,
    question_text TEXT NOT NULL, options JSONB,
    correct_answer TEXT NOT NULL, explanation TEXT,
    difficulty VARCHAR(10) DEFAULT 'medium',
    UNIQUE (video_id, ts_bucket_30s, prompt_version, question_text)
);

-- quiz_attempts: per-user responses
CREATE TABLE quiz_attempts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    question_id UUID NOT NULL REFERENCES questions(id),
    selected_answer TEXT NOT NULL, is_correct BOOLEAN NOT NULL,
    attempted_at TIMESTAMPTZ DEFAULT now()
);

-- review_queue: spaced repetition (per-user)
CREATE TABLE review_queue (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    question_id UUID NOT NULL REFERENCES questions(id),
    next_review_at TIMESTAMPTZ DEFAULT now(),
    interval_days INT DEFAULT 1, ease_factor FLOAT DEFAULT 2.5,
    repetitions INT DEFAULT 0,
    UNIQUE (user_id, question_id)
);
```

**Key design rules (non-negotiable):**
- Quiz cache key is GLOBAL: `(video_id, ts_bucket_30s, prompt_version)` — shared across users
- LLM pattern: Groq primary → Gemini fallback (same as `pipeline/answer.py`)
- `.env` has `GROQ_API_KEY` and `GEMINI_API_KEY`
- DB access: use `psycopg2` + `os.getenv("DATABASE_URL")`

---

## DB Data Available

6 videos indexed with ~716 chunks total. Example chunk format in `video_chunks`:
```python
{"chunk_id": "chunk_003", "text": "unit testing verifies...", "start_time": 30.0, "end_time": 40.0}
```

---

## Task 1: Checkpoint Placement

**Create file:** `pipeline/checkpoints.py`

```python
"""Place quiz checkpoints at topic-shift boundaries."""
import logging
import numpy as np

logger = logging.getLogger(__name__)

def place_checkpoints(
    chunks: list[dict],
    video_duration_seconds: float,
    embeddings: list | None = None,
    target_interval_minutes: float = 6.0,
) -> list[dict]:
    """
    Place checkpoints at semantic boundaries, ~1 per 5-8 minutes.

    Algorithm:
    1. target_count = max(1, round(duration / (target_interval * 60)))
    2. If embeddings given: cosine distance between consecutive chunks
       Else: use text length change as proxy
    3. Pick top target_count highest shifts
    4. Enforce minimum 3-minute spacing
    5. Generate topic label from first ~8 words of the chunk

    Returns list of:
    {"timestamp_seconds": float, "chunk_index": int, "topic_label": str, "shift_score": float}
    """
```

Implementation notes:
- `chunks` has `start_time`, `end_time`, `text` keys
- Cosine distance: `1 - dot(a, b) / (norm(a) * norm(b))`
- Minimum spacing: 180 seconds between any two checkpoints
- Topic label: first 8 words of chunk text + "..."
- Sort output by timestamp ascending

---

## Task 2: Question Generation

**Create file:** `pipeline/quiz_gen.py`

```python
"""Generate MCQ quiz questions from lecture content via LLM."""
import json, logging, os, re

logger = logging.getLogger(__name__)

QUIZ_PROMPT = """Based on this lecture content near timestamp {timestamp}:

{context}

Generate {count} multiple-choice questions. Each must:
- Test understanding, not memorization
- Have exactly 4 options (A, B, C, D)
- Have exactly one correct answer

Return ONLY a JSON array:
[{{"question_text": "...", "options": ["A: ...", "B: ...", "C: ...", "D: ..."],
   "correct_answer": "A", "explanation": "...", "difficulty": "medium"}}]"""

def generate_quiz_questions(
    video_id: str, timestamp: float, chunks: list[dict], count: int = 3
) -> list[dict]:
    """
    Generate MCQ questions from chunks near a timestamp.

    1. Find chunks within ±60s of timestamp (or nearest 5 if none in range)
    2. Assemble context text
    3. Call Groq Llama 3.3 70B (primary) → Gemini 2.0 Flash (fallback)
    4. Parse JSON response
    5. Return list of question dicts
    """
```

Implementation notes:
- Use `groq` library: `from groq import Groq; client = Groq(api_key=...)`
- Model: `"llama-3.3-70b-versatile"`, temperature 0.7, max_tokens 2000
- Gemini fallback: `from google import genai; client = genai.Client(api_key=...)`
- JSON parsing: try direct `json.loads`, fallback to regex `re.search(r'\[.*\]', text, re.DOTALL)`
- Keys from: `os.getenv("GROQ_API_KEY")`, `os.getenv("GEMINI_API_KEY")`

---

## Task 3: Global Quiz Cache

**Create file:** `pipeline/quiz_cache.py`

```python
"""Global quiz cache: (video_id, ts_bucket_30s, prompt_version) → questions."""
import json, logging, os, uuid
import psycopg2

logger = logging.getLogger(__name__)

def _db_url():
    return os.getenv("DATABASE_URL")

def get_cached_questions(video_id: str, ts_bucket: int, prompt_version: int = 1) -> list[dict] | None:
    """Return cached questions or None if cache miss."""
    conn = psycopg2.connect(_db_url())
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, question_text, options, correct_answer, explanation, difficulty
            FROM questions WHERE video_id = %s AND ts_bucket_30s = %s AND prompt_version = %s
        """, (video_id, ts_bucket, prompt_version))
        rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    return [
        {"id": str(r[0]), "question_text": r[1],
         "options": r[2] if isinstance(r[2], list) else json.loads(r[2]),
         "correct_answer": r[3], "explanation": r[4], "difficulty": r[5]}
        for r in rows
    ]

def cache_questions(video_id: str, ts_bucket: int, prompt_version: int, questions: list[dict]):
    """Insert generated questions into global cache."""
    conn = psycopg2.connect(_db_url())
    with conn.cursor() as cur:
        for q in questions:
            cur.execute("""
                INSERT INTO questions (id, video_id, ts_bucket_30s, prompt_version,
                    question_text, options, correct_answer, explanation, difficulty)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (video_id, ts_bucket_30s, prompt_version, question_text) DO NOTHING
            """, (str(uuid.uuid4()), video_id, ts_bucket, prompt_version,
                  q["question_text"], json.dumps(q["options"]),
                  q["correct_answer"], q.get("explanation", ""),
                  q.get("difficulty", "medium")))
    conn.commit(); conn.close()

def get_or_generate(video_id: str, timestamp: float, chunks: list[dict], prompt_version: int = 1) -> list[dict]:
    """Check cache → generate if miss → cache → return."""
    ts_bucket = int(timestamp // 30)
    cached = get_cached_questions(video_id, ts_bucket, prompt_version)
    if cached:
        logger.info(f"Quiz cache HIT: {video_id}@bucket{ts_bucket}")
        return cached
    logger.info(f"Quiz cache MISS: {video_id}@bucket{ts_bucket} — generating")
    from pipeline.quiz_gen import generate_quiz_questions
    questions = generate_quiz_questions(video_id, timestamp, chunks)
    cache_questions(video_id, ts_bucket, prompt_version, questions)
    # Re-fetch to get DB-assigned IDs
    return get_cached_questions(video_id, ts_bucket, prompt_version) or questions
```

---

## Task 4: SM-2 Lite

**Create file:** `pipeline/spaced_repetition.py`

```python
"""Simplified SM-2 spaced repetition algorithm."""

def sm2_update(is_correct: bool, repetitions: int, ease_factor: float, interval_days: int
) -> tuple[int, float, int]:
    """Returns (new_repetitions, new_ease_factor, new_interval_days)."""
    if is_correct:
        repetitions += 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = int(interval_days * ease_factor)
        ease_factor = max(1.3, ease_factor + 0.1)
    else:
        repetitions = 0
        interval_days = 1
        ease_factor = max(1.3, ease_factor - 0.2)
    return repetitions, ease_factor, interval_days
```

---

## Task 5: Tests

**Create file:** `tests/test_quiz.py`

```python
import pytest
from pipeline.spaced_repetition import sm2_update
from pipeline.checkpoints import place_checkpoints

def test_sm2_correct_increases_interval():
    r, ef, iv = sm2_update(True, 0, 2.5, 1)
    assert r == 1 and iv == 1
    r, ef, iv = sm2_update(True, r, ef, iv)
    assert r == 2 and iv == 6
    r, ef, iv = sm2_update(True, r, ef, iv)
    assert r == 3 and iv >= 15

def test_sm2_wrong_resets():
    r, ef, iv = sm2_update(False, 3, 2.5, 15)
    assert r == 0 and iv == 1

def test_sm2_ease_floor():
    _, ef, _ = sm2_update(False, 0, 1.3, 1)
    assert ef >= 1.3

def test_checkpoint_placement_basic():
    chunks = [{"chunk_id": f"c{i}", "text": f"content about topic {i}",
               "start_time": i*10, "end_time": (i+1)*10} for i in range(30)]
    cps = place_checkpoints(chunks, 300, target_interval_minutes=2)
    assert len(cps) >= 1
    assert all("timestamp_seconds" in cp for cp in cps)
    assert all("topic_label" in cp for cp in cps)

def test_checkpoint_minimum_spacing():
    chunks = [{"chunk_id": f"c{i}", "text": f"text {i}",
               "start_time": i*10, "end_time": (i+1)*10} for i in range(60)]
    cps = place_checkpoints(chunks, 600, target_interval_minutes=3)
    for i in range(1, len(cps)):
        gap = cps[i]["timestamp_seconds"] - cps[i-1]["timestamp_seconds"]
        assert gap >= 180, f"Spacing {gap}s < 180s minimum"

def test_checkpoint_empty_chunks():
    cps = place_checkpoints([], 0)
    assert cps == []

def test_checkpoint_short_video():
    chunks = [{"chunk_id": "c0", "text": "intro", "start_time": 0, "end_time": 10}]
    cps = place_checkpoints(chunks, 10)
    assert cps == []  # too short for checkpoints
```

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `pipeline/checkpoints.py` | Checkpoint placement at topic boundaries |
| 2 | `pipeline/quiz_gen.py` | LLM question generation (Groq → Gemini fallback) |
| 3 | `pipeline/quiz_cache.py` | Global cache: check → generate → store |
| 4 | `pipeline/spaced_repetition.py` | SM-2 lite algorithm |
| 5 | `tests/test_quiz.py` | Tests for SM-2 + checkpoints |

---

## Self-Critical Audit Plan

### Audit 1: All modules import clean
```bash
source .venv/bin/activate
python3 -c "from pipeline.checkpoints import place_checkpoints; print('checkpoints OK')"
python3 -c "from pipeline.quiz_gen import generate_quiz_questions; print('quiz_gen OK')"
python3 -c "from pipeline.quiz_cache import get_or_generate; print('quiz_cache OK')"
python3 -c "from pipeline.spaced_repetition import sm2_update; print('sm2 OK')"
```
**PASS:** All 4 print OK.

### Audit 2: Checkpoint placement works
```bash
python3 -c "
from pipeline.checkpoints import place_checkpoints
chunks = [{'chunk_id': f'c{i}', 'text': f'topic {i} content here for testing', 'start_time': i*10, 'end_time': (i+1)*10} for i in range(50)]
cps = place_checkpoints(chunks, 500)
for cp in cps:
    print(f'  {cp[\"timestamp_seconds\"]}s: {cp[\"topic_label\"]}')
print(f'Total: {len(cps)} checkpoints')
assert len(cps) >= 1, 'No checkpoints placed'
print('PASS')
"
```
**PASS:** Returns 1+ checkpoints with timestamps and labels.

### Audit 3: Question generation works (live LLM call)
```bash
python3 -c "
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'), override=True)
from pipeline.quiz_gen import generate_quiz_questions
chunks = [{'chunk_id': 'c1', 'text': 'Unit testing verifies individual functions produce correct output for given inputs. Each test provides known input and checks expected output.', 'start_time': 0, 'end_time': 10}]
qs = generate_quiz_questions('test', 5, chunks, count=1)
print(f'Generated {len(qs)} questions')
print(f'Q: {qs[0][\"question_text\"][:80]}')
print(f'Options: {len(qs[0][\"options\"])}')
print(f'Answer: {qs[0][\"correct_answer\"]}')
assert len(qs) >= 1
assert len(qs[0]['options']) == 4
assert qs[0]['correct_answer'] in ['A','B','C','D']
print('PASS')
"
```
**PASS:** Returns valid question with 4 options and correct answer letter.

### Audit 4: Cache round-trip works
```bash
python3 -c "
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'), override=True)
from pipeline.quiz_cache import get_cached_questions, cache_questions
import psycopg2

# Insert
cache_questions('__test_m1__', 0, 1, [
    {'question_text': 'Test Q?', 'options': ['A: x','B: y','C: z','D: w'],
     'correct_answer': 'A', 'explanation': 'test', 'difficulty': 'easy'}
])
# Retrieve
cached = get_cached_questions('__test_m1__', 0, 1)
assert cached is not None and len(cached) == 1
print(f'Cached: {cached[0][\"question_text\"]}')
assert 'id' in cached[0]  # has DB-assigned ID

# Cleanup
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
with conn.cursor() as cur:
    cur.execute(\"DELETE FROM questions WHERE video_id = '__test_m1__'\")
conn.commit(); conn.close()
print('PASS')
"
```
**PASS:** Cache stores, retrieves with ID, and cleans up.

### Audit 5: SM-2 tests pass
```bash
pytest tests/test_quiz.py -v 2>&1 | tail -15
```
**PASS:** All tests pass.

### Audit 6: Full test suite — no regressions
```bash
pytest -q 2>&1 | tail -10
```
**PASS:** No regressions.

---

## Worker Log

### Files created
- `pipeline/checkpoints.py` — `place_checkpoints()` with cosine-distance / length-shift fallback, 180s min spacing, topic-label snippet, sorted ascending.
- `pipeline/quiz_gen.py` — `generate_quiz_questions()`, Groq llama-3.3-70b-versatile primary → Gemini 2.0 Flash fallback, JSON parsing with regex fallback + ```json fence stripping.
- `pipeline/quiz_cache.py` — `get_cached_questions`, `cache_questions` (idempotent ON CONFLICT), `get_or_generate` (cache → gen → cache → re-fetch with IDs).
- `pipeline/spaced_repetition.py` — `sm2_update()` with EF floor 1.3.
- `tests/test_quiz.py` — 7 tests covering SM-2 + checkpoints.

### Audit 1 — clean imports ✅ PASS
```
checkpoints OK
quiz_gen OK
quiz_cache OK
sm2 OK
```

### Audit 2 — checkpoint placement ✅ PASS
```
  100.0s: topic 10 content here for testing
Total: 1 checkpoints
PASS
```

### Audit 3 — live LLM ✅ PASS (after model fix)
First attempt failed: Gemini key's GCP project has `gemini-2.0-flash` free quota capped at 0. Switched `quiz_gen.py` Gemini fallback model from `gemini-2.0-flash` → `gemini-2.5-flash` (matches `pipeline/answer.py`). Re-run with Groq disabled to force fallback path:
```
Generated 1 questions
Q: A developer is writing a new function and wants to ensure it behaves as expected under various conditions. Which of the following approaches best aligns with the purpose of unit testing as described in the lecture?
Options: ['A: Creating small, isolated tests...', 'B: Running the entire application...', "C: Asking a colleague to review...", 'D: Integrating the function into the main codebase...']
Answer: A
PASS
```
**Outstanding:** `GROQ_API_KEY` in `.env` is still expired — rotate at console.groq.com. Until then, primary path falls through to Gemini.

### Audit 4 — cache round-trip ✅ PASS
```
Cached: Test Q?
ID: df952190-812b-4599-ac80-f58c2a0da1b9
Options: ['A: x', 'B: y', 'C: z', 'D: w']
PASS
```

### Audit 5 — SM-2 + checkpoint tests ✅ PASS
```
tests/test_quiz.py::test_sm2_correct_increases_interval PASSED           [ 14%]
tests/test_quiz.py::test_sm2_wrong_resets PASSED                         [ 28%]
tests/test_quiz.py::test_sm2_ease_floor PASSED                           [ 42%]
tests/test_quiz.py::test_checkpoint_placement_basic PASSED               [ 57%]
tests/test_quiz.py::test_checkpoint_minimum_spacing PASSED               [ 71%]
tests/test_quiz.py::test_checkpoint_empty_chunks PASSED                  [ 85%]
tests/test_quiz.py::test_checkpoint_short_video PASSED                   [100%]
============================== 7 passed in 0.04s ===============================
```

### Audit 6 — full suite, no regressions ✅ PASS
Excluded pre-existing live-LLM e2e tests (`test_evaluator_live.py`, `test_e2e.py`, `test_e2e_v2.py`, `e2e_mac_m2.py`) that fail on the same dead API keys as Audit 3.
```
43 passed, 2 warnings in 46.96s
```
(Of these, 7 are the new quiz tests; 36 are pre-existing.)

