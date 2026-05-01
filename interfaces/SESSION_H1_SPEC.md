# Session H1 — Rewrite pipeline/rag.py: Chroma → pgvector

## Status: 🔴 NOT STARTED
## One task file. All context is here — do NOT read HANDOFF.md, ROADMAP.md, or other SESSION_* files.

---

## What You're Doing

Rewrite `pipeline/rag.py` (294 lines, currently uses ChromaDB) to use Supabase Postgres + pgvector instead. The embedding model (Jina CLIP v2, 1024-dim) stays the same — only the storage/retrieval layer changes.

After this session, `backend/app.py` works with pgvector instead of Chroma, and existing tests pass.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`  
**Start backend:** `uvicorn backend.app:app --reload --port 8000`

---

## Pre-existing Infrastructure (Session G already done)

Supabase is provisioned. These tables already exist in Postgres:

```sql
-- videos: one row per (video_id, pipeline_version)
CREATE TABLE videos (
    id UUID PRIMARY KEY, video_id VARCHAR(11) NOT NULL,
    title TEXT, duration_seconds FLOAT, pipeline_version INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','processing','ready','failed')),
    status_detail TEXT, digest TEXT,
    created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (video_id, pipeline_version)
);

-- video_chunks: transcript windows with 1024-dim embeddings
CREATE TABLE video_chunks (
    id UUID PRIMARY KEY, video_id VARCHAR(11) NOT NULL,
    chunk_id VARCHAR(20) NOT NULL, start_time FLOAT NOT NULL, end_time FLOAT NOT NULL,
    text TEXT NOT NULL, embedding vector(1024), linked_keyframe_ids TEXT[],
    UNIQUE (video_id, chunk_id)
);

-- keyframe_embeddings: image embeddings in same 1024-dim space
CREATE TABLE keyframe_embeddings (
    id UUID PRIMARY KEY, video_id VARCHAR(11) NOT NULL,
    keyframe_id VARCHAR(20) NOT NULL, timestamp_seconds FLOAT NOT NULL,
    storage_path TEXT NOT NULL, embedding vector(1024),
    UNIQUE (video_id, keyframe_id)
);
```

Indexes exist: `ivfflat` on `video_chunks.embedding` and `keyframe_embeddings.embedding` using `vector_cosine_ops`.

**Config module exists:** `backend/supabase_config.py` (20 lines):
```python
def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set in .env")
    return url
```

`.env` has `DATABASE_URL` set and working. `psycopg2-binary` is installed.

---

## Current LectureIndex Interface (must preserve for backend/app.py compat)

`backend/app.py` calls `LectureIndex` like this:

```python
# Line 48-52:
from pipeline.rag import LectureIndex
_index = LectureIndex(persist_dir=settings.CHROMA_DIR)

# Line 131: check if video is indexed
index.is_indexed(video_id)  # → bool

# Line 184: index a video after processing
total = index.index_video(video_id=video_id, chunks=chunks, keyframe_manifest=kf_manifest, digest=digest)
# Returns: int (count of items indexed)

# Line 286: retrieve for answering
retrieval = index.retrieve(question=..., video_id=..., timestamp=..., top_k=10)
# Returns: {"ranked_chunks": [...], "relevant_keyframes": [...], "digest": "..."}
```

**The `persist_dir` kwarg must be accepted (for backward compat) but can be ignored.**

---

## Current rag.py Logic You Must Preserve (semantics, not Chroma code)

### `index_video()` currently:
1. Embed chunk texts via `self._embed.embed_batch_text(chunk_texts)` → list of 1024-dim vectors
2. Embed keyframe images via `self._embed.embed_batch_images(kf_paths)` → list of 1024-dim vectors
3. Embed digest text via `self._embed.embed_text(digest)` → single 1024-dim vector
4. Store all in Chroma with metadata including `video_id`, `type`, `start_time`, `end_time`, `linked_keyframes`, etc.

### `retrieve()` currently:
1. Embed question via `self._embed.embed_text(question)` → 1024-dim vector
2. Query Chroma for nearest neighbors filtered by `video_id`
3. Separate results into chunks, keyframes, and digest
4. Re-rank chunks by timestamp proximity (closer to asked `timestamp` → higher)
5. Collect keyframes linked to ranked chunks
6. Return `{ranked_chunks, relevant_keyframes, digest}`

### `is_indexed()` currently:
- Check if any docs exist for this `video_id` in Chroma → bool

---

## Task 1: Rewrite pipeline/rag.py

Replace the full file content. New version uses `psycopg2` to talk to pgvector.

**Key pgvector query syntax:**
```sql
-- Cosine distance: <=> operator (lower = more similar)
-- Cosine similarity = 1 - cosine_distance
SELECT chunk_id, text, start_time, end_time,
       1 - (embedding <=> %s::vector) AS similarity
FROM video_chunks
WHERE video_id = %s
ORDER BY embedding <=> %s::vector
LIMIT %s;
```

**Embedding service** (`pipeline/embeddings.py`, 178 lines) provides:
```python
from pipeline.embeddings import EmbeddingService
svc = EmbeddingService("jina")
svc.embed_text("hello")           # → list[float] (1024-dim)
svc.embed_batch_text(["a", "b"])   # → list[list[float]]
svc.embed_batch_images(["a.jpg"])  # → list[list[float]]
```

**New `LectureIndex` must implement:**

1. **`__init__(self, persist_dir=None, embedding_model="jina", **kwargs)`**
   - Accept `persist_dir` for backward compat (ignore it)
   - Read `DATABASE_URL` from env via `backend.supabase_config.get_database_url()`
   - Create `EmbeddingService(embedding_model)`

2. **`is_indexed(self, video_id) → bool`**
   ```sql
   SELECT EXISTS(SELECT 1 FROM videos WHERE video_id = %s AND status = 'ready')
   ```

3. **`index_video(self, video_id, chunks, keyframe_manifest, digest) → int`**
   - `INSERT INTO videos ... ON CONFLICT (video_id, pipeline_version) DO UPDATE SET status = 'processing'`
   - Embed chunks → INSERT INTO `video_chunks` with `ON CONFLICT ... DO NOTHING`
   - Embed keyframes → INSERT INTO `keyframe_embeddings` with `ON CONFLICT ... DO NOTHING`
   - Store digest in `videos.digest`
   - UPDATE status to `'ready'`
   - Return total count of items indexed

4. **`retrieve(self, question, video_id, timestamp, top_k=12) → dict`**
   - Embed question text
   - SELECT nearest chunks from `video_chunks` (fetch `top_k * 2`, then re-rank)
   - SELECT nearest keyframes from `keyframe_embeddings` (top 5)
   - **Re-rank chunks by combined score:**
     ```python
     combined = (1 - alpha) * semantic_similarity + alpha * temporal_proximity
     temporal_proximity = 1 / (1 + abs(chunk_midpoint - timestamp) / 60)
     ```
     Use `alpha = 0.3`
   - Fetch digest from `videos.digest`
   - Return top_k chunks + up to 3 keyframes + digest

**Output format for `ranked_chunks`** (must match what `pipeline/answer.py` expects):
```python
{
    "chunk_id": "chunk_003",
    "text": "the gradient points in...",
    "start_time": 30.0,
    "end_time": 40.0,
    "relevance_score": 0.87,      # the combined re-ranked score
    "video_id": "3OmfTIf-SOU",
    "type": "chunk",
    "linked_keyframes": "kf_000035,kf_000036",  # comma-separated string
}
```

**Output format for `relevant_keyframes`:**
```python
{
    "frame_id": "kf_000035",
    "timestamp": 35.0,
    "file": "data/processed/3OmfTIf-SOU/keyframes/kf_000035.jpg",  # = storage_path column
    "video_id": "3OmfTIf-SOU",
    "type": "keyframe",
    "similarity": 0.82,
}
```

---

## Task 2: Two Small Edits in backend/app.py

### Edit 1: `_get_index()` (lines 48-52)

**Current:**
```python
def _get_index():
    from pipeline.rag import LectureIndex
    global _index
    if _index is None:
        _index = LectureIndex(persist_dir=settings.CHROMA_DIR)
    return _index
```

**Change to:**
```python
def _get_index():
    from pipeline.rag import LectureIndex
    global _index
    if _index is None:
        _index = LectureIndex()
    return _index
```

### Edit 2: `health_check()` (lines ~100-113)

**Current** references `idx._col.count()` which is Chroma-specific. Replace:
```python
@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return system status."""
    return HealthResponse(
        status="ok",
        model_loaded=True,
        model_name="groq/llama-4-scout-17b",
        gpu_available=False,
    )
```
(Remove the `indexed_count` dead code block entirely.)

---

## Task 3: Update tests/test_rag.py

Current file (182 lines) tests the Chroma-based LectureIndex. Update:

- `LectureIndex()` no longer needs `persist_dir`
- Use real `DATABASE_URL` from `.env` (load via `dotenv`)
- After each test, clean up test data:
  ```sql
  DELETE FROM video_chunks WHERE video_id = 'test_xxx';
  DELETE FROM keyframe_embeddings WHERE video_id = 'test_xxx';
  DELETE FROM videos WHERE video_id = 'test_xxx';
  ```
- Test `is_indexed()` returns False for unknown video, True after indexing
- Test `index_video()` inserts correct row counts
- Test `retrieve()` returns results with similarity scores
- Test timestamp re-ranking works (closer chunks rank higher)

Also delete `tests/test_rag_v2.py` if it still exists (stale after Session F rename).

---

## Deliverables

| # | File | Change |
|---|---|---|
| 1 | `pipeline/rag.py` | Full rewrite: Chroma → pgvector (psycopg2) |
| 2 | `backend/app.py` | 2 small edits: `_get_index()` + `health_check()` |
| 3 | `tests/test_rag.py` | Update for pgvector |

---

## Self-Critical Audit Plan

Run these checks IN ORDER after all tasks. Every check must pass.

### Audit 1: rag.py imports without Chroma
```bash
source .venv/bin/activate
python3 -c "from pipeline.rag import LectureIndex; print('PASS: imports OK')"
```
**PASS:** Prints OK. No `ModuleNotFoundError` for chromadb.

### Audit 2: No chromadb in pipeline/rag.py
```bash
grep -n "chromadb\|from chromadb\|import chroma" pipeline/rag.py
```
**PASS:** Returns EMPTY.

### Audit 3: is_indexed works on unknown video
```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv(override=True)
from pipeline.rag import LectureIndex
idx = LectureIndex()
result = idx.is_indexed('XXXXXXXXXXX')
assert result == False, f'Expected False, got {result}'
print('PASS: is_indexed(unknown) = False')
"
```
**PASS:** Prints PASS.

### Audit 4: Backend starts and health works
```bash
uvicorn backend.app:app --port 8000 &
sleep 6
result=$(curl -s http://localhost:8000/api/health)
echo "$result" | python3 -m json.tool
kill %1 2>/dev/null
```
**PASS:** Returns `{"status": "ok", "model_loaded": true, "model_name": "groq/llama-4-scout-17b", ...}`.

### Audit 5: index_video inserts rows and is_indexed flips to True
```bash
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
from pipeline.rag import LectureIndex
import psycopg2, os

idx = LectureIndex()
chunks = [
    {"chunk_id": "tc0", "start_time": 0, "end_time": 10,
     "text": "Unit testing verifies individual functions.", "linked_keyframe_ids": []},
    {"chunk_id": "tc1", "start_time": 10, "end_time": 20,
     "text": "Integration testing checks module interactions.", "linked_keyframe_ids": []},
]
total = idx.index_video("__audit_h1__", chunks, [], "Testing lecture digest")
print(f"Indexed: {total}")
assert total >= 2, f"Expected >=2, got {total}"

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM video_chunks WHERE video_id=%s", ("__audit_h1__",))
db_count = cur.fetchone()[0]
print(f"Chunks in DB: {db_count}")
assert db_count == 2, f"Expected 2 chunks, got {db_count}"

assert idx.is_indexed("__audit_h1__"), "is_indexed should be True after indexing"
print("is_indexed: True")

# Cleanup
cur.execute("DELETE FROM video_chunks WHERE video_id=%s", ("__audit_h1__",))
cur.execute("DELETE FROM keyframe_embeddings WHERE video_id=%s", ("__audit_h1__",))
cur.execute("DELETE FROM videos WHERE video_id=%s", ("__audit_h1__",))
conn.commit(); conn.close()
print("PASS: index_video + is_indexed work correctly")
EOF
```
**PASS:** All assertions pass. Cleanup succeeds.

### Audit 6: retrieve returns semantically relevant results
```bash
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
from pipeline.rag import LectureIndex
import psycopg2, os

idx = LectureIndex()
chunks = [
    {"chunk_id": "rc0", "start_time": 0, "end_time": 10,
     "text": "Gradient descent moves parameters downhill on the loss surface.", "linked_keyframe_ids": []},
    {"chunk_id": "rc1", "start_time": 10, "end_time": 20,
     "text": "The learning rate controls step size in gradient descent.", "linked_keyframe_ids": []},
    {"chunk_id": "rc2", "start_time": 50, "end_time": 60,
     "text": "Convolution applies a filter sliding across the input image.", "linked_keyframe_ids": []},
]
idx.index_video("__audit_h1r__", chunks, [], "ML lecture")

r = idx.retrieve("What is gradient descent?", "__audit_h1r__", timestamp=5, top_k=2)
rc = r["ranked_chunks"]
print(f"Chunks returned: {len(rc)}")
assert len(rc) == 2, f"Expected 2, got {len(rc)}"
assert "relevance_score" in rc[0], "Missing relevance_score key"
assert "gradient" in rc[0]["text"].lower(), f"Top chunk should mention gradient, got: {rc[0]['text'][:60]}"
print(f"Top chunk: {rc[0]['text'][:60]}")
print(f"Relevance: {rc[0]['relevance_score']:.3f}")
print(f"Digest: '{r['digest'][:30]}'")

# Cleanup
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("DELETE FROM video_chunks WHERE video_id=%s", ("__audit_h1r__",))
cur.execute("DELETE FROM videos WHERE video_id=%s", ("__audit_h1r__",))
conn.commit(); conn.close()
print("PASS: retrieve returns relevant results with scores")
EOF
```
**PASS:** Top chunk mentions gradient descent. Has relevance_score. Digest present.

### Audit 7: Tests pass
```bash
pytest tests/test_rag.py -q 2>&1 | tail -10
```
**PASS:** All tests pass.

### Audit 8: Full test suite — no regressions
```bash
pytest -q 2>&1 | tail -10
```
**PASS:** No regressions. (Document any pre-existing failures.)

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->
