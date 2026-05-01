# Session B — Library & Embedding Scenes (2, 3, 4, 8)

## Status: � COMPLETE
## One task only. Do NOT read other project files — all context is here.

## What you're doing

Build 4 scene files for the EduVidQA "Kitchen Tour" Manim explainer. All 4 scenes share the visual theme of **prep + library lookup** — Quill chunking transcript, Lens curating keyframes, Indie filing into the vector library, and (later in service) Indie retrieving from it. Building them in one session means you reuse the same `corkboard`, `drawer_wall`, and `vector_arrow` mobjects across files.

## Pre-flight

1. Activate venv: `source /Users/shubhamkumar/eduvidqa-product/.venv/bin/activate`
2. Confirm Session A's lib exists:
   ```bash
   ls scripts/explainer_v4_lib/ && ls scripts/explainer_v4/scene_01_cold_open.py
   ```
   If either missing → STOP. Session A is not done; do not proceed.
3. Read these and only these files (do not branch into other files):
   - `scripts/explainer_v4_lib/__init__.py`
   - `scripts/explainer_v4_lib/pi_chef.py`
   - `scripts/explainer_v4_lib/floorplan.py`
   - `scripts/explainer_v4_lib/speech_bubble.py`
   - `scripts/explainer_v4_lib/base_scene.py`
   - `scripts/explainer_v4/scene_01_cold_open.py` (as your reference for scene structure)

## Shared mobjects to put in your scene files (or local helper)

You may add a local helper file `scripts/explainer_v4/_shared_library.py` (only B owns this) with:
- `Corkboard(rows=2, cols=3)` — pinboard for keyframes (Scene 3, reused as backdrop in 4).
- `DrawerWall(n_rows=8, n_cols=12)` — grid of small `Square`s representing vector slots (Scenes 4, 8).
- `vector_arrow_from(text_mobject, target_drawer)` — animation of glowing arrow with coord label `[0.12, -0.44, ...]` flying into a specific drawer.

## Scenes (with full script extracts)

### Scene 2 — Quill chunks the transcript (10 s, 0:08–0:18)
File: `scripts/explainer_v4/scene_02_quill_chunks.py` · Class: `Scene02QuillChunks`
> **Visual:** Quill walks in carrying the canister. Unrolls it on a long table — it becomes a horizontal **ribbon of transcript text** with a parallel **strip of video frames** above it. Quill produces oversized scissors and snips the ribbon every 10 seconds. Each piece falls into a tray, stamped `[02:10 → 02:20]`, `[02:20 → 02:30]`...
> **Label:** `Quill — Transcript chunker · pipeline/chunking.py`
> **VO:** "First, the lecture is sliced into ten-second windows of text — small enough to retrieve precisely, big enough to carry context."

Implementation:
- Quill enters from screen-left carrying the `lecture.mp4` canister mobject (recreate locally — small `RoundedRectangle` labeled `lecture.mp4`).
- Ribbon = long thin `Rectangle` with 6 chunk markers; frame strip = 6 `Square`s above it.
- Scissor snips: 5 `Cut` animations (use `FadeOut` of a small `Line` indicator + slight separation). Each snipped pair (text + frame) drops into the tray with a stamp `[mm:ss → mm:ss]`.
- Use `lower_third_label` for the Quill tag.

### Scene 3 — Lens picks keyframes (12 s, 0:18–0:30)
File: `scripts/explainer_v4/scene_03_lens_keyframes.py` · Class: `Scene03LensKeyframes`
> **Visual:** Lens walks the frame strip with a magnifying glass labeled **"SSIM"**. Holds two adjacent frames side by side. If they look the same, *whoosh* — one crumples and tossed into a bin marked `0.92 similarity → discard`. If different (a new slide), *snap!* — frame is pinned to a corkboard. The corkboard fills with ~6 distinct slides.
> **Bubble (Lens, once):** *"Same slide. Skip."*
> **Label:** `Lens — Keyframe extractor · SSIM dedup`

Implementation:
- Reuse the frame strip from Scene 2 (recreate locally for independence).
- 8 frames total: 5 distinct, 3 duplicates. Run a `compare → decide → pin/discard` loop.
- Bin labeled `0.92 similarity → discard` on the right.
- Corkboard on the left fills row-by-row.
- Single `SpeechBubble("Same slide. Skip.")` on the third comparison only.

### Scene 4 — Indie files everything in the library (18 s, 0:30–0:48)
File: `scripts/explainer_v4/scene_04_indie_files.py` · Class: `Scene04IndieFiles`
> **Visual:** Camera pans right. A wall of tiny drawers — the **Vector Library**. Indie takes each transcript strip and each pinned frame, holds it up; a coordinate vector `[0.12, –0.44, 0.81, …]` floats out and the item slides itself into a drawer at that location. Text strips and frame photos go into the *same* library — visualized as both landing in nearby drawers.
> **Bubble (Indie):** *"Same space. Text and pixels."*
> **Label:** `Indie — Chroma + Jina CLIP v2 (text + image, 1024-dim)`

Implementation:
- Camera move: `self.camera.frame.animate.shift(RIGHT * 4)` over 1 s.
- `DrawerWall(8, 12)` fills the right side.
- Process 4 items (2 transcript strips + 2 frame photos). Each: Indie holds it up → coord label `Text("[0.12, -0.44, 0.81, ...]", font_size=20)` floats out → item slides into a specific drawer (highlight that drawer with `Indicate`).
- Text and frame items land in **adjacent** drawers — visually proves shared space.

### Scene 8 — Indie embeds + retrieves (22 s, 1:18–1:40)
File: `scripts/explainer_v4/scene_08_indie_retrieves.py` · Class: `Scene08IndieRetrieves`
> **Visual:** Indie reads the ticket aloud silently. The question text on the ticket lifts off as glowing letters, condenses into a glowing arrow with a coordinate label `[0.31, –0.07, …]`. Indie walks the arrow into the library, stops at one drawer, slides it open: **a tray of 10 transcript scrolls + 3 photos** rises out, glowing with similarity scores.
> **Bubble (Indie):** *"Top 10. Plus three frames."*

Implementation:
- Recreate `OrderTicket(question="Why does the gradient point uphill?", timestamp="04:32", video_id="3OmfTIf-SOU")` from the lib.
- Question text lifts off → morphs (`Transform`) into a glowing arrow + coord label.
- Indie walks arrow to one specific drawer in the wall, opens it (slide-out animation).
- A tray rises holding 10 mini-scrolls + 3 mini-photos, each tagged with a faint similarity score (0.74, 0.71, ...).

## Steps

For EACH of the 4 scenes, in this exact order (one scene fully done before starting the next):
1. Implement the scene file inheriting from `BaseScene`.
2. Render at -ql:
   ```bash
   manim -ql scripts/explainer_v4/scene_0X_<name>.py Scene0X<Name>
   ```
3. Verify duration with `ffprobe`. Target ± 1 s of the listed duration.
4. **Visual QC** — extract 2 keyframes (mid + end) at NATIVE resolution + MAX quality:
   ```bash
   SCENE=scene_0X_<name> && CLASS=Scene0X<Name>
   QC=media/qc/$SCENE && mkdir -p "$QC"
   IN=media/videos/$SCENE/480p15/$CLASS.mp4
   DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
   ffmpeg -y -ss $(echo "$DUR/2" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/mid.jpg" 2>/dev/null
   ffmpeg -y -ss $(echo "$DUR-0.3" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/end.jpg" 2>/dev/null
   ```
   No `-vf scale`, `-q:v 2` → native-res, near-lossless JPEGs (~120 KB each) for Director-grade review.
   Call `view_image` on each. Confirm scene-specific elements (e.g. for Scene 3 — corkboard with pinned frames + discard bin visible at end frame).
5. If render fails, duration is wildly off, OR visual QC reveals missing/broken elements, fix code and re-render.

Render commands (run sequentially, with QC after each):
```bash
cd /Users/shubhamkumar/eduvidqa-product
manim -ql scripts/explainer_v4/scene_02_quill_chunks.py Scene02QuillChunks
manim -ql scripts/explainer_v4/scene_03_lens_keyframes.py Scene03LensKeyframes
manim -ql scripts/explainer_v4/scene_04_indie_files.py Scene04IndieFiles
manim -ql scripts/explainer_v4/scene_08_indie_retrieves.py Scene08IndieRetrieves
```

## Constraints

- **Image budget: 8 small JPEGs total** (2 per scene × 4 scenes) — at the 8-small-image safe limit. Do NOT exceed. To debug a bad frame: fix code, re-render, re-extract the same 2 frames.
- Native resolution (854×480), `-q:v 2` quality. ~120 KB per frame.
- Do NOT modify anything in `scripts/explainer_v4_lib/` — that's Session A's territory. If a helper is missing, raise it in your Worker Log and work around it locally instead of editing the lib.
- Do NOT touch any other scene files (5, 6, 7, 9–15) — those belong to other sessions.
- All 4 scene files must be self-contained (no imports between scene files except via `_shared_library.py` which only B owns).

## Worker Log

### Pre-flight
- Confirmed Session A artifacts present: `scripts/explainer_v4_lib/{__init__,palette,floorplan,pi_chef,order_ticket,speech_bubble,base_scene}.py` and `scripts/explainer_v4/scene_01_cold_open.py`. Read only the 6 files listed in the spec; no branching.

### Implementation notes
- Added `scripts/explainer_v4/_shared_library.py` (Session B local) exporting `Corkboard`, `DrawerWall`, and `vector_arrow_from(...)`. Reused across Scenes 3 (Corkboard), 4 + 8 (DrawerWall + vector_arrow_from).
- All 4 scene files inherit from `BaseScene` and use the same `sys.path.insert(...)` pattern as `scene_01_cold_open.py`, so `manim` works when invoked from the repo root.
- No edits to anything in `scripts/explainer_v4_lib/` (Session A territory). No edits to other scenes.
- Lower-third character labels rendered via the lib's `lower_third_label` helper for first-entrance scenes (2, 3, 4). Scene 8 uses the on-screen `OrderTicket` mobject instead of an extra label.
- Duration tuning was iterative: render → `ffprobe` → adjust per-beat `run_time` until each scene landed inside its ±1 s window.

### Bugs found in Visual QC and fixed
- **Scene 3 (first QC pass)**: pinned keyframes appeared at world-origin instead of on the corkboard. Two root causes in `_shared_library.Corkboard`:
  1. The slot `Square`s were created and stored in `self.cells` but never `add()`ed to the parent `VGroup`. Caller's `.move_to(...)` therefore translated only the board + title, leaving slot positions stuck at construction-time coordinates. → Fixed by `self.add(slot)` inside the cell-build loop, plus a docstring on `slot_position()` clarifying it returns *live* world-space centers.
  2. After the fix, slots translated correctly but pinned frames rendered *behind* the corkboard board (because the board was added to the scene later via `FadeIn`, putting it on top). → Fixed in `scene_03_lens_keyframes.py` by setting `target_frame.set_z_index(5)` before pinning. Re-render verified: end frame shows 5 distinct colored slides pinned on the board.
- **Scene 2 / Scene 4 start-frame appears black/empty in QC**: not a code bug — `start.jpg` is sampled at 0.3 s, before the lower-third / camera pan introduces content. Mid + end frames confirm the scenes are correct.

### Audit Report

| Scene | File | Lines | Render exit | Duration (s) | Target ±1s | Pass |
|---|---|---:|:---:|---:|---|:---:|
| 2 | `scripts/explainer_v4/scene_02_quill_chunks.py`     | 167 | 0 |  9.267 | 10 (9–11)  | ✅ |
| 3 | `scripts/explainer_v4/scene_03_lens_keyframes.py`   | 182 | 0 | 12.733 | 12 (11–13) | ✅ |
| 4 | `scripts/explainer_v4/scene_04_indie_files.py`      | 160 | 0 | 17.666 | 18 (17–19) | ✅ |
| 8 | `scripts/explainer_v4/scene_08_indie_retrieves.py`  | 210 | 0 | 21.466 | 22 (21–23) | ✅ |
| — | `scripts/explainer_v4/_shared_library.py` (helper) | 161 | — | — | — | — |

Render commands (each exited 0):
```
manim -ql scripts/explainer_v4/scene_02_quill_chunks.py     Scene02QuillChunks
manim -ql scripts/explainer_v4/scene_03_lens_keyframes.py   Scene03LensKeyframes
manim -ql scripts/explainer_v4/scene_04_indie_files.py      Scene04IndieFiles
manim -ql scripts/explainer_v4/scene_08_indie_retrieves.py  Scene08IndieRetrieves
```

ffprobe verification (raw):
```
scene_02_quill_chunks.py     | exit=0 | duration=9.266667s
scene_03_lens_keyframes.py   | exit=0 | duration=12.733011s
scene_04_indie_files.py      | exit=0 | duration=17.666344s
scene_08_indie_retrieves.py  | exit=0 | duration=21.465689s
```

### Visual QC — 8 native-res keyframes total (2 per scene), stored in `media/qc/<scene>/{mid,end}.jpg`

Per the updated spec: extracted at native 854×480 resolution with `-q:v 2` (~10–17 KB each — well-compressed despite no `-vf scale`). Old 480-wide thumbnail `start.jpg` files removed from my four `media/qc/scene_0[2348]_*` folders to keep the budget at 8.

**Scene 2 — Quill chunks the transcript**
- `mid.jpg`: Quill (sky-blue pi) on left labeled `Quill`; full ribbon of 5 remaining transcript chunks + 5 frame squares above; tray (`chunks/`) below holding the first snipped pair.
- `end.jpg`: 5 snipped (text + frame) pairs lined up inside the tray, each with its `[mm:ss → mm:ss]` stamp; tray label `chunks/` on right; Quill still on left holding nothing.

**Scene 3 — Lens picks keyframes**
- `mid.jpg`: Lens (peach pi) with `SSIM` magnifier hovering over the strip; remaining strip shows B, C, C, D, D, E; corkboard (left, "Keyframes") with slide A pinned in slot (0,0); discard bin (right) labeled `0.92 similarity → discard` containing one shrunk dimmed duplicate.
- `end.jpg`: 5 distinct colored slides (A, B, C, D, E) pinned across the corkboard slots; discard bin contains a dimmed duplicate; Lens + magnifier hovering past the (now empty) strip. **Scene 3 corkboard bug confirmed fixed.**

**Scene 4 — Indie files everything in the library**
- `mid.jpg`: DrawerWall (8×12, `Vector Library` label) on right; Indie (lavender pi, `Indie`) centered; yellow vector arrow + coord label `[ 0.13, -0.42, 0.79, ...]` flying into a specific drawer (with prior item already embedded as a small blue square inside the target).
- `end.jpg`: DrawerWall fully visible; 4 drawers contain embedded shrunk items in two adjacent text+frame pairs (rows 3 cols 4–5 and rows 5 cols 7–8); Indie at hold position; arrow + coord faded out.

**Scene 8 — Indie embeds + retrieves**
- `mid.jpg`: Indie centered; OrderTicket above (`Why does the gradient ...`, `t=04:32`, `3OmfTIf-SOU`); long yellow arrow spans across to a drawer in the wall (`Vector Library` on right).
- `end.jpg`: DrawerWall on right with one drawer slid open; tray risen above the drawer holding 10 mini-scrolls (2 rows × 5) + 3 mini-photos on a third row, each with similarity-score label (subtle peach `#FFD27F` text); Indie + ticket centered.

## Self-Audit
- [x] All 4 scene files exist with real content
- [x] All 4 -ql renders exit 0 (see table)
- [x] All 4 mp4 durations within ± 1 s of target (see table)
- [x] Visual QC done for all 4 scenes — **8** native-res keyframes (2 per scene) extracted to `media/qc/scene_0[2348]_*/{mid,end}.jpg`, viewed, and described per-scene above (within the 8-image budget)
- [x] No edits outside assigned files (`_shared_library.py` + 4 scene files; 0 edits to `explainer_v4_lib/` or other scenes)
- [x] Audit Report (above) lists file paths, line counts, render exit codes, durations, and QC frame descriptions
