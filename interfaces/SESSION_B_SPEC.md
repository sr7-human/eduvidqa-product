# Session B: Embeddings + ChromaDB + Lecture Digest

## Status
- **Assigned:** Worker Session B
- **Dependencies:** BLOCKED — Needs Session A output (keyframes + chunks in data/processed/)
- **Last updated:** April 1, 2026

---

## ⚠️ MANAGER INSTRUCTIONS (READ THIS FIRST)

Read `/memories/session/munimi.md` for full project context. You build the RETRIEVAL layer — embeddings, vector storage, and the Lecture Digest.

**WAIT** until Session A has completed and updated their spec file. Check for their "Worker Updates" section in `interfaces/SESSION_A_SPEC.md`.

Working directory: `/Users/shubhamkumar/eduvidqa-product/`
Python venv: `.venv/bin/python`

Test videos (same 3 as Session A):
- `3OmfTIf-SOU`, `VRcixOuG-TU`, `oZgbwa8lvDE`

Processed data from Session A should be in: `data/processed/{video_id}/`

**When done:** Update the "Worker Updates" section at the bottom of THIS file.

---

## Task 1: Dual Embedding Module (pipeline/embeddings_v2.py)

### What to build
A module that embeds BOTH text AND images using two models:
- **PRIMARY: Jina CLIP v2** — local, free, no quota, 1024-dim
- **SECONDARY: Gemini Embedding 2** — API, higher quality, 768-dim

### How it works

**Jina CLIP v2 (primary):**
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("jinaai/jina-clip-v2", trust_remote_code=True)
text_emb = model.encode("what is sorting?")          # 1024-dim
img_emb = model.encode(Image.open("kf_000035.jpg"))  # 1024-dim, SAME space!
```

**Gemini Embedding 2 (secondary):**
```python
from google import genai
from google.genai import types
client = genai.Client(api_key="GEMINI_API_KEY_FROM_ENV")
result = client.models.embed_content(
    model="gemini-embedding-2-preview",
    contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")],
    config=types.EmbedContentConfig(output_dimensionality=768)
)
```

### Function signatures
```python
class EmbeddingService:
    def __init__(self, model: str = "jina"):
        """model: 'jina' (local) or 'gemini' (API)"""

    def embed_text(self, text: str) -> list[float]
    def embed_image(self, image_path: str) -> list[float]
    def embed_batch_text(self, texts: list[str]) -> list[list[float]]
    def embed_batch_images(self, paths: list[str]) -> list[list[float]]
    def get_dimension(self) -> int  # 1024 for jina, 768 for gemini
```

### Dependencies
```bash
.venv/bin/pip install sentence-transformers Pillow
# google-genai already installed
```

### Key rule
- Cannot MIX embeddings from different models in the same ChromaDB collection
- Config flag `EMBEDDING_MODEL=jina|gemini` decides which to use
- Default to `jina` (free, no quota issues)

---

## Task 2: ChromaDB Indexing + Retrieval (pipeline/rag_v2.py)

### What to build
A new RAG module that indexes transcript chunks, keyframes, and digest into ChromaDB. Performs hybrid retrieval at query time.

### How it works
1. One ChromaDB collection per embedding model: `eduvidqa_jina` or `eduvidqa_gemini`
2. Each document has metadata: `{video_id, type: "chunk"|"keyframe"|"digest", timestamp, chunk_id}`
3. Index: embed transcript chunks + keyframe images + digest text → store in ChromaDB
4. Retrieve: embed question → cosine search → filter by video_id → rank by proximity to timestamp

### Function signatures
```python
class LectureIndex:
    def __init__(self, persist_dir: str = "data/chroma", embedding_model: str = "jina"):

    def index_video(self, video_id: str, chunks: list[dict], keyframe_manifest: list[dict], digest: str) -> int:
        """Index all content for one video. Returns count of embeddings stored."""

    def retrieve(self, question: str, video_id: str, timestamp: float, top_k: int = 12) -> dict:
        """
        Returns:
        {
            "ranked_chunks": [...],      # 10-sec chunks ranked by proximity to timestamp
            "relevant_keyframes": [...], # keyframes from semantic search + linked to chunks
            "digest": "...",             # full lecture digest text
        }
        """

    def is_indexed(self, video_id: str) -> bool
```

### Retrieval logic (important!)
1. Embed the question using the same model (Jina or Gemini)
2. Search ChromaDB filtered by `video_id`
3. Get top-K results (mix of chunks + keyframes)
4. RE-RANK chunks by proximity to the asked timestamp:
   - The chunk whose time window contains `timestamp` comes FIRST
   - Adjacent chunks follow in order of distance
5. Always include the digest (retrieve it by `type="digest"` filter)
6. Return linked keyframes from the retrieved chunks + any semantically matched keyframes

---

## Task 3: Lecture Digest Generation (pipeline/digest.py)

### What to build
Generate a comprehensive Lecture Digest from the full transcript + all keyframes.

### How it works
1. Read `data/processed/{video_id}/transcript/full.txt`
2. Read all keyframe images from `data/processed/{video_id}/keyframes/`
3. Send transcript + keyframe images to Groq Llama 4 Scout (vision model)
4. Groq API key: `GROQ_API_KEY_FROM_ENV`
5. Save output as `data/processed/{video_id}/digest.txt`

### Prompt
```
Create a detailed, comprehensive digest of this entire lecture.

This is NOT a summary — do NOT shorten or condense. Capture ALL:
- Key concepts explained
- Formulas, code, algorithms shown
- Diagrams and visual content described from the frames
- Examples given by the professor
- Important definitions and terminology

The transcript and lecture frames are provided below.
```

### Important: Groq image limits
- Groq may limit images per request. If sending 50+ keyframes fails:
  - Batch: send 5 keyframes at a time with portions of the transcript
  - Merge the partial digests into one final document

### Function
```python
def generate_digest(video_id: str, data_dir: str = "data/processed") -> str:
    """Returns the full digest text. Also saves to data/processed/{video_id}/digest.txt"""
```

---

## Task 4: Integration Test

Run the full pipeline on all 3 videos:
1. Load Session A's keyframes + chunks from `data/processed/`
2. Generate digest for each video
3. Embed everything (using Jina CLIP v2 primary)
4. Index into ChromaDB
5. Test retrieval: ask 2 questions per video, verify results make sense

Create test script: `tests/test_rag_v2.py`

---

## Worker Updates
<!-- Worker: Write your results below this line after completing tasks -->

**April 1, 2026 — All 4 tasks complete**

### Files created
- `pipeline/embeddings_v2.py` — Dual embedding service (Jina CLIP v2 local 1024-dim + Gemini Embedding 2 API 768-dim)
- `pipeline/rag_v2.py` — ChromaDB indexing + retrieval with timestamp-proximity re-ranking, keyframe linking, digest storage
- `pipeline/digest.py` — Groq Llama 4 Scout digest generation with batched keyframe handling
- `tests/test_rag_v2.py` — Integration test suite

### Jina CLIP v2 compatibility fix
- PyTorch 2.11 + transformers 5.4 cause a meta tensor crash in Jina's EVA vision tower (`torch.linspace().item()`)
- Patched automatically in `embeddings_v2.py._patch_jina_eva_model()` — replaces with pure Python linspace
- Required deps: `einops`, `timm`, `torchvision`

### ChromaDB collections
```
eduvidqa_jina (792 total):
  3OmfTIf-SOU:  56 items (29 chunks + 26 keyframes + 1 digest)
  VRcixOuG-TU: 144 items (78 chunks + 65 keyframes + 1 digest)
  oZgbwa8lvDE: 592 items (145 chunks + 446 keyframes + 1 digest)

eduvidqa_gemini (792 total):
  3OmfTIf-SOU:  56 items (29 chunks + 26 keyframes + 1 digest)
  VRcixOuG-TU: 144 items (78 chunks + 65 keyframes + 1 digest)
  oZgbwa8lvDE: 592 items (145 chunks + 446 keyframes + 1 digest)
```
Both collections fully indexed and consistent.

### Embedding model consistency
- **Vector embeddings** (ChromaDB): Jina CLIP v2 (1024-dim) and Gemini Embedding 2 `gemini-embedding-2-preview` (768-dim). One collection per model. NO mixing.
- **Digest generation** (LLM text generation, NOT embeddings): Groq Llama 4 Scout for 2 videos, Gemini 2.5 Flash for `oZgbwa8lvDE` (Groq daily TPD limit hit). The digest is plain text that then gets embedded by the respective embedding model into ChromaDB.

### Digests
- `3OmfTIf-SOU`: 5,686 chars ✓ (generated by Groq Llama 4 Scout)
- `VRcixOuG-TU`: 3,427 chars ✓ (generated by Groq Llama 4 Scout)
- `oZgbwa8lvDE`: 10,428 chars ✓ (generated by Gemini 2.5 Flash — Groq was rate-limited)

### Retrieval verification (2 questions per video, both models)
```
3OmfTIf-SOU — "What is unit testing?"
  [Jina]   top: "unit testing. Unit tests test a single unit of functionality..."
  [Gemini] top: "unit testing. Unit tests test a single unit of functionality..."

VRcixOuG-TU — "What is a perceptron?"
  [Jina]   top: "the Perceptron Learning Algorithm. We now see a more principled..."
  [Gemini] top: "the Perceptron Learning Algorithm. We now see a more principled..."

oZgbwa8lvDE — "How does insertion sort work?"
  [Jina]   top: "sorted array... output of any sorting algorithm..."
  [Gemini] top: "sorting algorithms sorting problems..."
```
All queries return ranked chunks + linked keyframes + digest. ✓

### Known issue
- `oZgbwa8lvDE` has 446 keyframes (SSIM threshold too loose for animated sorting content). Session A quality issue — works but slow to embed (~13 min for Gemini API, ~7 min for Jina local).
