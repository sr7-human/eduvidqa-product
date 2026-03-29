# Session E: Integration & Deploy Worker — Interface Specification

## Status
- **Assigned:** Not yet started
- **Dependencies:** BLOCKED — needs ALL sessions (A+B+C+D) completed
- **Last updated:** March 29, 2026

---

## Your Mission
Wire all pipeline modules (Ingest → RAG → Inference) behind a FastAPI backend, deploy to HuggingFace Spaces (backend + model) and Vercel (frontend), and run end-to-end tests.

## Context
We're building an AI Teaching Assistant for YouTube lectures (EduVidQA paper, EMNLP 2025). Sessions A-D built individual modules. YOUR job is to:
1. Create the FastAPI backend that orchestrates everything
2. Deploy backend + model to HuggingFace Spaces (free, ZeroGPU)
3. Deploy frontend to Vercel (free)
4. Make sure the whole thing works end-to-end

## Hardware
- MacBook Air M2 16GB (local dev + testing)
- HuggingFace Spaces ZeroGPU (production backend — free A10G bursts)
- Vercel free tier (production frontend)

## Files You Create
```
backend/
├── app.py                   # FastAPI application
├── models.py                # Request/response Pydantic models (API layer)
├── config.py                # Environment config
└── requirements.txt         # Backend Python dependencies

Dockerfile                   # For HuggingFace Spaces deployment
README_HF.md                 # HuggingFace Spaces readme (app card)
vercel.json                  # Vercel config for frontend
requirements.txt             # Root-level combined requirements
tests/test_e2e.py            # End-to-end integration tests
```

## API Endpoints You Implement

### `POST /api/ask` — Main endpoint
```python
@app.post("/api/ask")
async def ask_question(request: AskRequest) -> AskResponse:
    """
    Full pipeline: URL + question → AI answer.
    
    1. Check if video is already cached/indexed
    2. If not, run ingest pipeline (Session A)
    3. Run RAG retrieval (Session B)  
    4. Run inference (Session C)
    5. Optionally score quality
    6. Return answer
    """
    pass
```

**Request:**
```python
class AskRequest(BaseModel):
    youtube_url: str          # Full YouTube URL
    timestamp: float          # Seconds
    question: str             # Student's question
    skip_quality_eval: bool = False  # Skip scoring to save time
```

**Response:**
```python
class AskResponse(BaseModel):
    question: str
    answer: str
    video_id: str
    sources: list[SourceInfo]
    quality_scores: QualityScores | None
    model_name: str
    generation_time_seconds: float

class SourceInfo(BaseModel):
    start_time: float
    end_time: float
    relevance_score: float
```

### `POST /api/process-video` — Pre-process a video
```python
@app.post("/api/process-video")
async def process_video(request: ProcessRequest) -> ProcessResponse:
    """
    Download + index a video ahead of time.
    Useful for pre-caching popular lectures.
    """
    pass
```

### `GET /api/health` — Health check
```python
@app.get("/api/health")
async def health_check() -> HealthResponse:
    """Return system status: model loaded, GPU available, etc."""
    pass
```

## Key Requirements

### 1. FastAPI Setup
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="EduVidQA API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vercel frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Orchestration Logic
The `/api/ask` endpoint orchestrates the full pipeline:
```
youtube_url → extract video_id
→ if not index.is_indexed(video_id):
    → ingest_video(youtube_url)          # Session A
    → index.index_segments(segments)      # Session B
→ retrieval = index.retrieve(question, video_id, top_k=5)  # Session B
→ answer = engine.generate_answer(retrieval)                 # Session C
→ if not skip_quality_eval:
    → scores = evaluator.score(question, answer.answer)      # Session C
→ return AskResponse(...)
```

### 3. Model Lifecycle
- Load model on startup (or lazy-load on first request)
- On HuggingFace Spaces with ZeroGPU, use `@spaces.GPU` decorator for GPU functions
- Keep model in memory between requests (no reload per request)
- Timeout: 120 seconds max per request

### 4. HuggingFace Spaces Deployment
```python
# For ZeroGPU support, the app needs gradio OR the spaces SDK
# Option A: Pure FastAPI with ZeroGPU
# Option B: Gradio interface (simpler for HF Spaces, still exposes API)

# Recommended: Use Gradio as the HF Spaces wrapper, expose FastAPI alongside
# This gives you: free ZeroGPU + a nice UI on HF Spaces + API endpoint
```

**Dockerfile for HF Spaces:**
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 7860
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

### 5. Vercel Deployment
- Frontend built by Session D lives in `frontend/`
- `vercel.json` configures the build
- Environment variable `VITE_API_URL` points to HF Spaces URL

### 6. Error Handling
- Invalid YouTube URLs → 400 with clear message
- Private/age-restricted videos → 403 with explanation
- Model not loaded → 503 with retry-after
- Timeout → 504 with partial result if available

## Dependencies (pip install)
```
fastapi
uvicorn[standard]
pydantic
python-multipart

# Pipeline modules (from Sessions A-C)
youtube-transcript-api
yt-dlp
ffmpeg-python
sentence-transformers
chromadb
transformers>=4.45.0
bitsandbytes
accelerate
qwen-vl-utils
torch
Pillow
```

## Test Criteria
```python
# End-to-end test
import httpx

BASE = "http://localhost:8000"

# 1. Health check
r = httpx.get(f"{BASE}/api/health")
assert r.json()["status"] == "ok"

# 2. Process a video
r = httpx.post(f"{BASE}/api/process-video", json={
    "youtube_url": "https://www.youtube.com/watch?v=SHORT_VIDEO_ID"
})
assert r.status_code == 200
assert r.json()["segment_count"] > 0

# 3. Ask a question
r = httpx.post(f"{BASE}/api/ask", json={
    "youtube_url": "https://www.youtube.com/watch?v=SHORT_VIDEO_ID",
    "timestamp": 60,
    "question": "What concept is being explained here?"
}, timeout=120)
assert r.status_code == 200
data = r.json()
assert len(data["answer"]) > 50
assert data["quality_scores"] is not None or data["quality_scores"] is None
assert len(data["sources"]) > 0
```

---

## Worker Updates (Session E fills this in)

### Progress Log
<!-- Worker: Add your updates below this line -->

