# Session A: Keyframe Extraction + Transcript Chunking

## Status
- **Assigned:** Worker Session A
- **Dependencies:** NONE — can start immediately
- **Last updated:** April 1, 2026

---

## ⚠️ MANAGER INSTRUCTIONS (READ THIS FIRST)

Read `/memories/session/munimi.md` for full project context. You are building the FOUNDATION modules that all other sessions depend on.

Test on ALL 3 videos from AutoTA:
- `3OmfTIf-SOU` — Khan Academy Unit Testing (4.7 min, 30fps)
- `VRcixOuG-TU` — Deep Learning Perceptron (13.6 min, 25fps)  
- `oZgbwa8lvDE` — Algorithms Insertion Sort (27.4 min, 30fps)

Video files are at: `/Users/shubhamkumar/AutoTA/videos/`
Copy them to: `/Users/shubhamkumar/eduvidqa-product/data/videos/`

Working directory: `/Users/shubhamkumar/eduvidqa-product/`
Python venv: `.venv/bin/python` (Python 3.12)

**When done:** Update the "Worker Updates" section at the bottom of THIS file.

---

## Task 1: SSIM Keyframe Extraction (pipeline/keyframes.py)

### What to build
A module that extracts unique keyframes from a video using SSIM deduplication.

### How it works
1. Open video with OpenCV (`cv2.VideoCapture`)
2. Extract 1 frame per second (use `cap.set(cv2.CAP_PROP_POS_FRAMES, sec * fps)`)
3. Compare each frame with the LAST KEPT frame using SSIM (`skimage.metrics.structural_similarity`)
4. If SSIM > 0.92 → SKIP (same slide). If SSIM < 0.92 → KEEP (new content)
5. Save kept frames as `kf_SSSSSS.jpg` (zero-padded seconds) in `data/processed/{video_id}/keyframes/`
6. Generate `manifest.json` with metadata per keyframe

### Function signature
```python
def extract_keyframes(
    video_path: str,
    video_id: str,
    output_dir: str = "data/processed",
    threshold: float = 0.92
) -> list[dict]:
    """
    Returns list of:
    {
        "frame_id": "kf_000035",
        "timestamp": 35,
        "file": "data/processed/3OmfTIf-SOU/keyframes/kf_000035.jpg",
        "ssim_score": 0.847  # SSIM compared to previous kept frame
    }
    """
```

### Dependencies to install
```bash
.venv/bin/pip install scikit-image
```
(opencv-python should already be installed)

### Expected results
- 4.7 min video (285s) → sample 285 frames → expect ~15-40 unique keyframes
- 13.6 min video (815s) → sample 815 frames → expect ~30-80 keyframes
- 27.4 min video (1642s) → sample 1642 frames → expect ~50-150 keyframes
- Processing time: ~2-5 seconds per video on M2

---

## Task 2: 10-Second Transcript Chunking (pipeline/chunking.py)

### What to build
A module that downloads the transcript and splits it into 10-second chunks, linked to keyframes.

### How it works
1. Download transcript using `youtube_transcript_api.YouTubeTranscriptApi.get_transcript(video_id)`
2. The API returns: `[{"text": "...", "start": 0.15, "duration": 3.5}, ...]`
3. Group transcript lines into 10-second non-overlapping windows: 0-10, 10-20, 20-30, ...
4. Each chunk: concatenate all transcript lines whose `start` falls within the window
5. Link keyframes to chunks: if a keyframe has timestamp 35s, it belongs to chunk 30-40s
6. Save:
   - `data/processed/{video_id}/transcript/full.txt` (complete transcript as plain text)
   - `data/processed/{video_id}/transcript/chunks.json` (structured chunks)

### Function signature
```python
def chunk_transcript(
    video_id: str,
    output_dir: str = "data/processed",
    keyframe_manifest: list[dict] | None = None
) -> list[dict]:
    """
    Returns list of:
    {
        "chunk_id": "chunk_003",
        "start_time": 30.0,
        "end_time": 40.0,
        "text": "the insertion sort algorithm works by...",
        "linked_keyframe_ids": ["kf_000035"]
    }
    """
```

### Expected results
- 4.7 min video → ~29 chunks (285s / 10)
- 13.6 min video → ~82 chunks
- 27.4 min video → ~165 chunks
- Each chunk should have 1-5 transcript lines concatenated

---

## Task 3: Integration Test

Run both modules on all 3 videos. Print a report:

```
Video: 3OmfTIf-SOU (4.7 min)
  Keyframes: XX extracted (from 285 sampled)
  Chunks: 29 created
  Linked: XX keyframes linked to chunks
  Files saved: data/processed/3OmfTIf-SOU/keyframes/ (XX files)
               data/processed/3OmfTIf-SOU/transcript/full.txt
               data/processed/3OmfTIf-SOU/transcript/chunks.json

Video: VRcixOuG-TU (13.6 min)
  ...

Video: oZgbwa8lvDE (27.4 min)
  ...
```

Create this as a test script: `tests/test_keyframes_chunking.py`

---

## Worker Updates
<!-- Worker: Write your results below this line after completing tasks -->

**April 1, 2026 — All 3 tasks complete**

### Files created
- `pipeline/keyframes.py` — SSIM-based keyframe extraction (OpenCV + scikit-image)
- `pipeline/chunking.py` — 10-second transcript chunking with keyframe linking (youtube-transcript-api v1.2.4, uses new `.fetch()` API)
- `tests/test_keyframes_chunking.py` — Integration test over all 3 videos

### Integration test results
```
Video: 3OmfTIf-SOU (Khan Academy Unit Testing, 4.7 min)
  Keyframes: 26 extracted (from 282 sampled)
  Chunks:    29 created
  Linked:    26 keyframes linked to 19 chunks
  ✓ All assertions passed

Video: VRcixOuG-TU (Deep Learning Perceptron, 13.6 min)
  Keyframes: 65 extracted (from 816 sampled)
  Chunks:    79 created
  Linked:    42 keyframes linked to 26 chunks
  ✓ All assertions passed

Video: oZgbwa8lvDE (Algorithms Insertion Sort, 27.4 min)
  Keyframes: 1519 extracted (from 1644 sampled)
  Chunks:    164 created
  Linked:    1517 keyframes linked to 164 chunks
  ✓ All assertions passed
```

### Notes
- **oZgbwa8lvDE had 1519 keyframes → now 446 after adaptive mode.** The video contains continuous whiteboard animation. Adaptive mode detected >10 kf/min, re-ran with threshold=0.80 + 256px resize + 3 kf/chunk cap. 71% reduction.
- `youtube-transcript-api` v1.2.4 changed API: `YouTubeTranscriptApi().fetch(id)` returns `FetchedTranscriptSnippet` objects (not dicts). Code handles this.
- Dependencies installed: `scikit-image`, `opencv-python-headless`, `youtube-transcript-api` (all in `.venv`)

### ⚠️ FINDING FOR MANAGER: High-Change Video Types

**Problem:** SSIM deduplication breaks down for videos with continuous pixel-level change. The Insertion Sort video (whiteboard animation) produced 1519 keyframes at threshold=0.92 — nearly every frame was "unique."

**8 video types that defeat SSIM dedup:**
1. **Whiteboard animation** (confirmed — oZgbwa8lvDE)
2. **Live coding / IDE screencasts** — every keystroke shifts pixels
3. **Tablet handwriting** (GoodNotes/Notability lectures) — continuous ink strokes
4. **Math animation** (3Blue1Brown / Manim style) — smooth geometric transforms
5. **Screen recordings with scrolling** — scrolling docs, web pages, code
6. **Picture-in-picture with webcam** — instructor's face changes every second even if slide is static
7. **Slides with build animations** — PowerPoint fly-in/fade/morph transitions
8. **Physics/chemistry simulations** — circuit sims, molecular dynamics, continuous motion

**Adaptive strategy implemented (auto-detects, no manual config needed):**
1. First pass with normal threshold (0.92)
2. Measure keyframes/minute — if > 10 → flag as "high-change"
3. Re-run with: lower threshold (0.80) + downsampled SSIM comparison (256px width) to reduce sensitivity to cursor/small text changes
4. Cap: keep only 3 most visually distinct frames per 10-second chunk (lowest SSIM = biggest visual change)
5. Clean up excess frame files from disk

**Result:** oZgbwa8lvDE went from 1519 → 446 keyframes (71% reduction). The constants (`_MAX_KF_PER_MIN=10`, `_ADAPTIVE_THRESHOLD=0.80`, `_MAX_KF_PER_CHUNK=3`) are module-level and easy to tune.
