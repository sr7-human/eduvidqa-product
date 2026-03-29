# Session C: Inference Worker — Interface Specification

## Status
- **Assigned:** Not yet started
- **Dependencies:** BLOCKED — needs Session A + B output formats finalized
- **Last updated:** March 29, 2026

---

## Your Mission
Load Qwen2.5-VL-7B-Instruct (4-bit quantized), build the prompt template, and generate educational answers from retrieved video context. Also build quality evaluation (Clarity/ECT/UPT scoring).

## Context
We're building an AI Teaching Assistant for YouTube lectures (EduVidQA paper, EMNLP 2025). Sessions A+B produce `RetrievalResult` (top-K relevant video segments with transcripts + frame paths). YOUR job is to:
1. Load Qwen2.5-VL-7B with 4-bit quantization (~5GB memory)
2. Build a prompt that feeds transcript + frames + question
3. Generate a clear, pedagogical answer
4. Score the answer on Clarity/ECT/UPT using the paper's Likert scales

## Hardware
- MacBook Air M2 16GB (local dev — model runs on MPS/CPU, slow but works)
- HuggingFace Spaces ZeroGPU (production — free A10G/T4 bursts)
- Kaggle 2×T4 (alternative for batch inference, 30hrs/week free)

## Files You Create
```
pipeline/inference.py        # Model loading + answer generation
pipeline/prompts.py          # Prompt templates
pipeline/evaluate.py         # Clarity/ECT/UPT scoring
notebooks/inference_kaggle.ipynb  # Kaggle notebook for GPU inference
tests/test_inference.py      # Unit tests
```

## Input Data Model (from Session B)

```python
class RetrievedContext(BaseModel):
    segment: VideoSegment        # Has: transcript_text, frame_paths, start_time, end_time
    relevance_score: float
    rank: int

class RetrievalResult(BaseModel):
    query: str                   # Student's question
    video_id: str
    contexts: list[RetrievedContext]
    total_segments: int
```

## Output Data Model (YOU define these — add to pipeline/models.py)

```python
class QualityScores(BaseModel):
    """Likert scale scores (1-5) from the EduVidQA paper."""
    clarity: float              # 1-5: Is the answer clear and jargon-free?
    ect: float                  # 1-5: Does it encourage critical thinking?
    upt: float                  # 1-5: Does it use pedagogical techniques?

class AnswerResult(BaseModel):
    """Final output: the AI-generated answer with metadata."""
    question: str
    answer: str                  # The generated educational answer
    video_id: str
    sources: list[dict]          # [{start_time, end_time, relevance_score}] — which segments were used
    quality_scores: QualityScores | None  # None if scoring is skipped
    model_name: str              # "Qwen/Qwen2.5-VL-7B-Instruct"
    generation_time_seconds: float
```

## Functions You Implement

### `pipeline/prompts.py`

```python
SYSTEM_PROMPT = """You are an expert AI teaching assistant helping students understand lecture videos. 
Your answers must be:
1. CLEAR — explain every technical term, use simple language, logical flow
2. COMPLETE — cover the concept fully using the provided lecture context
3. PEDAGOGICAL — use examples, analogies, step-by-step breakdowns where helpful
4. ACCURATE — only state facts supported by the lecture content provided

You have access to the lecture transcript and video frames around the student's question.
"""

def build_answer_prompt(question: str, contexts: list[RetrievedContext]) -> list[dict]:
    """
    Build the multimodal prompt for Qwen2.5-VL.
    
    Returns list of message dicts in the format Qwen2.5-VL expects:
    [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "...context..."},
            {"type": "image", "image": "file:///path/to/frame.jpg"},
            ...
            {"type": "text", "text": "Student question: ..."}
        ]}
    ]
    """
    pass

EVAL_PROMPT_TEMPLATE = """Rate the following answer on a scale of 1-5 for each quality:

Question: {question}
Answer: {answer}

Rate EACH on 1-5:
1. Clarity (1=jargon-filled, incoherent → 5=crystal clear, logical, beginner-friendly)
2. ECT - Encouraging Critical Thinking (1=purely factual → 5=poses follow-ups, discusses alternatives)  
3. UPT - Uses Pedagogical Techniques (1=no examples → 5=rich examples, analogies, step-by-step)

Return JSON only: {{"clarity": X, "ect": X, "upt": X}}
"""
```

### `pipeline/inference.py`

```python
class QwenInference:
    """Qwen2.5-VL-7B inference engine."""
    
    def __init__(self, model_name: str = "Qwen/Qwen2.5-VL-7B-Instruct", quantize_4bit: bool = True):
        """
        Load model with 4-bit quantization.
        Uses bitsandbytes on GPU, or MPS/CPU fallback on Mac.
        """
        pass
    
    def generate_answer(
        self, 
        retrieval_result: RetrievalResult,
        max_new_tokens: int = 4096,
        temperature: float = 0.3
    ) -> AnswerResult:
        """
        Generate an educational answer from retrieved context.
        
        1. Build prompt from retrieval_result (transcript + frames + question)
        2. Run inference
        3. Return structured AnswerResult
        """
        pass
    
    def unload(self):
        """Free GPU/MPS memory."""
        pass
```

### `pipeline/evaluate.py`

```python
class QualityEvaluator:
    """Score answers on Clarity/ECT/UPT using the EduVidQA paper's Likert scales."""
    
    def __init__(self, method: str = "hf_inference"):
        """
        method options:
        - "hf_inference": Use HuggingFace free Inference API (Qwen2.5-72B-Instruct)
        - "local": Use the same local Qwen2.5-VL-7B (less accurate but no API needed)
        - "groq": Use Groq free API (Llama 3.3 70B, fast)
        """
        pass
    
    def score(self, question: str, answer: str) -> QualityScores:
        """Score an answer on Clarity/ECT/UPT. Returns QualityScores."""
        pass
```

## Key Requirements

1. **Model loading**: Use `transformers` + `bitsandbytes` for 4-bit quantization. Model ID: `Qwen/Qwen2.5-VL-7B-Instruct`. On Mac M2, use `device_map="mps"` or `"cpu"` with float16. On GPU (HF Spaces/Kaggle), use 4-bit NF4 quantization.

2. **Multimodal prompt**: Qwen2.5-VL accepts interleaved text + images. Feed the top-5 retrieved segments' transcripts AND up to 3 key frames per segment (max 15 frames total). Use `qwen_vl_utils` for image preprocessing.

3. **Answer quality**: Target >3.5 Clarity on the paper's Likert scale. System prompt should emphasize clarity and pedagogical techniques.

4. **Max tokens**: Set to 4096 (the paper used only 256 — we're doing much better).

5. **Temperature**: Use 0.3 for factual educational content (low creativity, high accuracy).

6. **Evaluation**: The quality scorer is SEPARATE from the answer generator. Use a larger model (72B via free API) to judge the 7B model's output. This mirrors the paper's approach (they used GPT-4o as evaluator).

## Likert Scale Definitions (from the paper)

### Clarity (1-5)
- 1: ≥2 jargon terms without explanation AND ≥2 incoherent transitions
- 2: ≥2 jargon terms without explanation OR ≥2 incoherent transitions  
- 3: ≤1 jargon term without explanation AND ≤1 incoherent transition, but improvable
- 4: No unexplained jargon, logical structure, minor improvements possible
- 5: Crystal clear, perfectly structured, beginner-friendly

### ECT (1-5)
- 1: No questions, no alternatives, purely factual
- 2: One surface-level question or suggestion
- 3: Meaningful question or alternative approach discussed
- 4: Multiple thought-provoking elements + why-questions
- 5: Deep critical engagement, challenges assumptions, open-ended exploration

### UPT (1-5)  
- 1: Pure explanation without any example or breakdown
- 2: One basic example
- 3: Good example with some step-by-step breakdown
- 4: Multiple examples + analogies + clear breakdown  
- 5: Rich pedagogical approach — examples, analogies, visualizations, step-by-step

## Dependencies (pip install)
```
transformers>=4.45.0
bitsandbytes
accelerate
qwen-vl-utils
torch
Pillow
pydantic
huggingface_hub  # for free inference API
```

## Test Criteria
```python
# Test with mock retrieval result
from pipeline.models import VideoSegment, RetrievedContext, RetrievalResult

mock_result = RetrievalResult(
    query="How does backpropagation work?",
    video_id="test123",
    contexts=[
        RetrievedContext(
            segment=VideoSegment(
                video_id="test123", segment_index=0,
                start_time=120, end_time=240,
                transcript_text="Backpropagation works by computing gradients...",
                frame_paths=["test_frame.jpg"]
            ),
            relevance_score=0.92, rank=1
        )
    ],
    total_segments=10
)

engine = QwenInference(quantize_4bit=True)
answer = engine.generate_answer(mock_result)

assert len(answer.answer) > 100          # Non-trivial answer
assert answer.model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
assert answer.generation_time_seconds > 0
assert len(answer.sources) > 0

# Test quality scoring
evaluator = QualityEvaluator(method="hf_inference")
scores = evaluator.score(answer.question, answer.answer)
assert 1 <= scores.clarity <= 5
assert 1 <= scores.ect <= 5
assert 1 <= scores.upt <= 5
```

---

## Worker Updates (Session C fills this in)

### Progress Log
<!-- Worker: Add your updates below this line -->

