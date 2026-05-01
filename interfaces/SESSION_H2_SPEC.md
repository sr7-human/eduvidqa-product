# Session H2 — Migrate Existing Videos to pgvector + Supabase Storage

## Status: 🔴 NOT STARTED
## Dependencies: H1 ✅ (rag.py rewritten for pgvector), G ✅ (DB tables exist)
## One task file. All context is here — do NOT read other files.

---

## What You're Doing

5 videos are already processed locally in `data/processed/`. The pgvector DB is **empty** (0 chunks, 0 keyframes, 0 videos). You need to re-embed and insert all 5 videos into Supabase Postgres, and upload their keyframe images to Supabase Storage bucket `keyframes` (already created).

After this session, all 5 videos are queryable via the pgvector-backed `LectureIndex`, and keyframe images are in Supabase Storage.

**Working directory:** `/Users/shubhamkumar/eduvidqa-product/`  
**Python venv:** `source .venv/bin/activate`

---

## Current State

**Local data (in `data/processed/`):**

| video_id | chunks | keyframes | digest.txt |
|---|---|---|---|
| `3OmfTIf-SOU` | 29 | 26 | ✅ yes |
| `VRcixOuG-TU` | 79 | 65 | ✅ yes |
| `VZYNneIHXJw` | 358 | 716 | ❌ no |
| `aircAruvnKk` | 111 | 125 | ❌ no |
| `oZgbwa8lvDE` | 164 | 446 | ✅ yes |

Each video dir has:
- `transcript/chunks.json` — array of `{chunk_id, start_time, end_time, text, linked_keyframe_ids}`
- `keyframes/manifest.json` — array of `{frame_id, timestamp, file, ssim_score}`
- `keyframes/*.jpg` — actual keyframe images
- `digest.txt` (some videos) — lecture digest text

**Supabase DB:** All 8 tables exist. All empty. `DATABASE_URL` is in `.env`.  
**Supabase Storage:** Bucket `keyframes` exists (private).  
**`backend/supabase_config.py`:** Provides `get_database_url()` and `get_supabase_client()`.  
**`pipeline/rag.py`:** Has `LectureIndex` with `index_video(video_id, chunks, keyframe_manifest, digest)` that inserts into pgvector.

---

## Task 1: Create Migration Script

**Create file:** `scripts/migrate_to_pgvector.py`

```python
"""One-time migration: embed & insert existing processed videos into Supabase pgvector."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from pipeline.rag import LectureIndex

PROCESSED_DIR = Path("data/processed")


def migrate_video(video_id: str, index: LectureIndex) -> bool:
    vid_dir = PROCESSED_DIR / video_id

    # Load chunks
    chunks_path = vid_dir / "transcript" / "chunks.json"
    if not chunks_path.exists():
        print(f"  SKIP: no chunks.json")
        return False
    chunks = json.loads(chunks_path.read_text())

    # Load keyframe manifest
    manifest_path = vid_dir / "keyframes" / "manifest.json"
    keyframes = json.loads(manifest_path.read_text()) if manifest_path.exists() else []

    # Load digest
    digest = ""
    digest_path = vid_dir / "digest.txt"
    if digest_path.exists():
        digest = digest_path.read_text().strip()

    # Index via LectureIndex (embeds + inserts into pgvector)
    total = index.index_video(video_id=video_id, chunks=chunks,
                               keyframe_manifest=keyframes, digest=digest)
    print(f"  ✓ {total} items indexed ({len(chunks)} chunks + {len(keyframes)} keyframes)")
    return True


def main():
    index = LectureIndex()

    video_dirs = sorted([
        d.name for d in PROCESSED_DIR.iterdir()
        if d.is_dir() and (d / "transcript").exists()
    ])
    print(f"Found {len(video_dirs)} videos to migrate: {video_dirs}\n")

    success = 0
    for vid in video_dirs:
        print(f"Migrating {vid}...")
        if index.is_indexed(vid):
            print(f"  SKIP: already indexed")
            success += 1
            continue
        try:
            if migrate_video(vid, index):
                success += 1
        except Exception as e:
            print(f"  FAIL: {e}")

    print(f"\nDone: {success}/{len(video_dirs)} videos migrated.")


if __name__ == "__main__":
    main()
```

**Run it:**
```bash
cd /Users/shubhamkumar/eduvidqa-product
source .venv/bin/activate
python scripts/migrate_to_pgvector.py
```

**⚠️ This will take time** — embedding 741 chunks + 1378 keyframes with Jina CLIP v2. Expect 5-15 minutes total depending on machine. Do NOT interrupt mid-video.

---

## Task 2: Upload Keyframes to Supabase Storage

**Create file:** `scripts/upload_keyframes_storage.py`

```python
"""Upload local keyframe JPEGs to Supabase Storage bucket 'keyframes'."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from backend.supabase_config import get_supabase_client

PROCESSED_DIR = Path("data/processed")


def upload_for_video(video_id: str, client) -> int:
    kf_dir = PROCESSED_DIR / video_id / "keyframes"
    manifest_path = kf_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"  SKIP: no manifest.json")
        return 0

    manifest = json.loads(manifest_path.read_text())
    uploaded = 0
    for kf in manifest:
        local_file = Path(kf["file"])
        if not local_file.is_file():
            continue
        remote_path = f"{video_id}/{kf['frame_id']}.jpg"
        try:
            with open(local_file, "rb") as f:
                client.storage.from_("keyframes").upload(
                    remote_path, f, {"content-type": "image/jpeg"}
                )
            uploaded += 1
        except Exception as e:
            err = str(e)
            if "Duplicate" in err or "already exists" in err:
                uploaded += 1  # already there
            else:
                print(f"    WARN {kf['frame_id']}: {err[:80]}")
    return uploaded


def main():
    client = get_supabase_client()
    video_dirs = sorted([
        d.name for d in PROCESSED_DIR.iterdir()
        if d.is_dir() and (d / "keyframes").exists()
    ])

    total = 0
    for vid in video_dirs:
        print(f"Uploading keyframes for {vid}...")
        n = upload_for_video(vid, client)
        print(f"  → {n} keyframes uploaded")
        total += n

    print(f"\nTotal: {total} keyframes uploaded to Supabase Storage.")


if __name__ == "__main__":
    main()
```

**Run it:**
```bash
python scripts/upload_keyframes_storage.py
```

---

## Task 3: Remove chromadb Dependency

After migration is verified working:

1. **Remove from `requirements.txt`:**
   ```bash
   # Find and remove the chromadb line
   grep -n "chromadb" requirements.txt
   # Then edit to remove it
   ```

2. **Verify no Python file imports chromadb:**
   ```bash
   grep -rn "chromadb\|import chroma" --include="*.py" .
   ```
   Should return EMPTY (or only comments).

3. **Delete stale test files if they exist:**
   ```bash
   rm -f tests/test_rag_v2.py tests/test_e2e.py
   ```

---

## Deliverables

| # | File | What |
|---|---|---|
| 1 | `scripts/migrate_to_pgvector.py` | Migration script — embeds + inserts all 5 videos |
| 2 | `scripts/upload_keyframes_storage.py` | Uploads keyframe JPEGs to Supabase Storage |
| 3 | `requirements.txt` | `chromadb` line removed |
| 4 | Stale test files deleted | `test_rag_v2.py`, `test_e2e.py` if they exist |

---

## Self-Critical Audit Plan

### Audit 1: All 5 videos in DB with status 'ready'
```bash
source .venv/bin/activate
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
import psycopg2, os
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT video_id, status FROM videos ORDER BY video_id")
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]}")
assert len(rows) == 5, f"Expected 5 videos, got {len(rows)}"
assert all(r[1] == 'ready' for r in rows), f"Not all ready: {rows}"
print(f"PASS: {len(rows)} videos, all ready")
conn.close()
EOF
```
**PASS:** 5 videos listed, all with status `ready`.

### Audit 2: Chunk counts match local data
```bash
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
import psycopg2, os
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT video_id, COUNT(*) FROM video_chunks GROUP BY video_id ORDER BY video_id")
rows = cur.fetchall()
expected = {"3OmfTIf-SOU": 29, "VRcixOuG-TU": 79, "VZYNneIHXJw": 358, "aircAruvnKk": 111, "oZgbwa8lvDE": 164}
for vid, cnt in rows:
    exp = expected.get(vid, "?")
    status = "✓" if cnt == exp else f"✗ (expected {exp})"
    print(f"  {vid}: {cnt} chunks {status}")
total = sum(r[1] for r in rows)
print(f"Total chunks: {total}")
assert total >= 700, f"Expected ~741 total chunks, got {total}"
print("PASS")
conn.close()
EOF
```
**PASS:** Chunk counts match or are close to expected (minor differences OK if some chunks had empty text).

### Audit 3: Keyframe embeddings exist
```bash
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
import psycopg2, os
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT video_id, COUNT(*) FROM keyframe_embeddings GROUP BY video_id ORDER BY video_id")
rows = cur.fetchall()
for vid, cnt in rows:
    print(f"  {vid}: {cnt} keyframes")
total = sum(r[1] for r in rows)
print(f"Total keyframe embeddings: {total}")
assert total > 0, "No keyframe embeddings!"
print("PASS")
conn.close()
EOF
```
**PASS:** Total > 0. Some keyframes may fail if files are missing — that's OK as long as most are there.

### Audit 4: Retrieval works end-to-end
```bash
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
from pipeline.rag import LectureIndex
idx = LectureIndex()
r = idx.retrieve("what is unit testing?", "3OmfTIf-SOU", timestamp=60, top_k=5)
print(f"Chunks: {len(r['ranked_chunks'])}")
print(f"Top: {r['ranked_chunks'][0]['text'][:80]}...")
print(f"Score: {r['ranked_chunks'][0]['relevance_score']:.3f}")
print(f"Keyframes: {len(r['relevant_keyframes'])}")
print(f"Digest: {'yes' if r['digest'] else 'no'} ({len(r['digest'])} chars)")
assert len(r['ranked_chunks']) >= 3, "Too few chunks returned"
print("PASS")
EOF
```
**PASS:** Returns relevant chunks about unit testing with non-zero scores.

### Audit 5: Full API flow works
```bash
uvicorn backend.app:app --port 8000 &
sleep 6
curl -s -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"youtube_url":"https://www.youtube.com/watch?v=3OmfTIf-SOU","question":"What is unit testing?","timestamp":60,"skip_quality_eval":true}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Answer: {d[\"answer\"][:150]}...'); print(f'Sources: {len(d[\"sources\"])}'); print(f'Time: {d[\"generation_time_seconds\"]}s')"
kill %1 2>/dev/null
```
**PASS:** Returns a real answer with sources and generation time. No 500.

### Audit 6: Keyframes in Supabase Storage
```bash
python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv(override=True)
from backend.supabase_config import get_supabase_client
c = get_supabase_client()
files = c.storage.from_("keyframes").list("3OmfTIf-SOU")
print(f"Keyframes in storage for 3OmfTIf-SOU: {len(files)}")
assert len(files) > 0, "No keyframes uploaded!"
print(f"First: {files[0]['name']}")
print("PASS")
EOF
```
**PASS:** Returns > 0 keyframe files.

### Audit 7: No chromadb in codebase
```bash
grep -rn "chromadb" --include="*.py" . --include="*.txt" . | grep -v "__pycache__"
```
**PASS:** Returns EMPTY (or only in `requirements.txt` comments).

### Audit 8: Tests pass
```bash
pytest -q 2>&1 | tail -10
```
**PASS:** No regressions. (Document any pre-existing failures.)

---

## Worker Log
<!-- Worker: Paste ALL audit terminal outputs below this line before marking complete. -->
