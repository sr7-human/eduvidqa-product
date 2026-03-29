# Session B: RAG Pipeline Worker — Interface Specification

## Status
- **Assigned:** Not yet started
- **Dependencies:** None — can start immediately (parallel with Session A)
- **Last updated:** March 29, 2026

---

## Your Mission
Build the RAG (Retrieval-Augmented Generation) pipeline that embeds transcript chunks into vectors, stores them in ChromaDB, and retrieves the most relevant chunks for a student's question.

## Context
We're building an AI Teaching Assistant for YouTube lectures (EduVidQA paper, EMNLP 2025). Session A produces `VideoSegment` objects (2-min chunks with transcript + frame paths). YOUR job is to:
1. Embed those chunks into vectors
2. Store them in a vector database
3. When a student asks a question, find the top-K most relevant chunks

## Hardware
- MacBook Air M2 16GB (local dev)
- HuggingFace Spaces 2-vCPU 16GB (production)
- NO GPU required for this module — embeddings run on CPU (M2 is fast enough)

## Files You Create
```
pipeline/rag.py             # Main RAG module (index + retrieve)
pipeline/embeddings.py      # Embedding model wrapper
tests/test_rag.py           # Unit tests
```

## Input Data Model (from Session A — defined in pipeline/models.py)

```python
class VideoSegment(BaseModel):
    video_id: str
    segment_index: int
    start_time: float
    end_time: float
    transcript_text: str
    frame_paths: list[str]
```

## Output Data Model (YOU define these — add to pipeline/models.py)

```python
class RetrievedContext(BaseModel):
    """A single retrieved chunk with relevance score."""
    segment: VideoSegment           # The original segment
    relevance_score: float          # Cosine similarity (0-1)
    rank: int                       # 1-based rank

class RetrievalResult(BaseModel):
    """Output of the retrieval pipeline."""
    query: str                      # Original student question
    video_id: str
    contexts: list[RetrievedContext]  # Top-K results, sorted by relevance
    total_segments: int              # How many segments were searched
```

## Functions You Implement

### `pipeline/embeddings.py`

```python
class EmbeddingModel:
    """Wrapper around sentence-transformers embedding model."""
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        """Load embedding model. Falls back to all-MiniLM-L6-v2 if OOM."""
        pass
    
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns vector."""
        pass
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently. Returns list of vectors."""
        pass
```

### `pipeline/rag.py`

```python
class LectureIndex:
    """Vector index for a single lecture video's segments."""
    
    def __init__(self, persist_dir: str = "./data/chroma"):
        """Initialize ChromaDB client and embedding model."""
        pass
    
    def index_segments(self, segments: list[VideoSegment]) -> int:
        """
        Embed and store all segments for a video.
        
        Args:
            segments: List of VideoSegment objects from Session A
            
        Returns:
            Number of segments indexed
        """
        pass
    
    def is_indexed(self, video_id: str) -> bool:
        """Check if a video has already been indexed (avoid re-embedding)."""
        pass
    
    def retrieve(
        self, 
        query: str, 
        video_id: str, 
        top_k: int = 5
    ) -> RetrievalResult:
        """
        Find the top-K most relevant segments for a student question.
        
        Args:
            query: Student's question text
            video_id: Which video to search in
            top_k: Number of results to return
            
        Returns:
            RetrievalResult with ranked contexts
        """
        pass
    
    def delete_video(self, video_id: str) -> bool:
        """Remove all indexed segments for a video (cleanup)."""
        pass
```

## Key Requirements

1. **Embedding model**: Use `BAAI/bge-m3` (sentence-transformers). It's 568M params, runs well on M2 CPU. If memory issues, fall back to `all-MiniLM-L6-v2` (22M params). BGE-M3 note: prepend instruction "Represent this educational lecture content: " to documents and "Represent this student question for retrieval: " to queries for best results.

2. **ChromaDB setup**: 
   - Use persistent storage (SQLite on disk at `./data/chroma/`)
   - One collection per video: collection name = `video_{video_id}`
   - Store metadata with each embedding: `{ "video_id": ..., "segment_index": ..., "start_time": ..., "end_time": ..., "transcript_text": ... }`

3. **Chunking strategy**: Session A already chunks by 2-minute segments. But if a segment's transcript is very long (>500 words), split it into sub-chunks with 1-sentence overlap. Store the parent segment reference in metadata.

4. **Retrieval**: 
   - Cosine similarity search
   - Return top_k results sorted by relevance
   - Include the full `VideoSegment` object in each result (so Session C can access frame paths)

5. **Caching**: If `is_indexed(video_id)` returns True, skip re-embedding.

## Dependencies (pip install)
```
sentence-transformers
chromadb
pydantic
torch  # CPU only, no CUDA needed
```

## Test Criteria
```python
# Create mock segments
segments = [
    VideoSegment(video_id="test123", segment_index=0, start_time=0, end_time=120,
                 transcript_text="Today we'll discuss backpropagation in neural networks...",
                 frame_paths=["frame_0.jpg"]),
    VideoSegment(video_id="test123", segment_index=1, start_time=120, end_time=240,
                 transcript_text="Gradient descent works by computing partial derivatives...",
                 frame_paths=["frame_1.jpg"]),
    # ... more segments
]

index = LectureIndex()
count = index.index_segments(segments)
assert count == len(segments)
assert index.is_indexed("test123")

result = index.retrieve("How does backpropagation work?", video_id="test123", top_k=3)
assert len(result.contexts) <= 3
assert result.contexts[0].relevance_score >= result.contexts[1].relevance_score  # Sorted
assert "backpropagation" in result.contexts[0].segment.transcript_text.lower()  # Relevant
```

---

## Worker Updates (Session B fills this in)

### Progress Log
<!-- Worker: Add your updates below this line -->

