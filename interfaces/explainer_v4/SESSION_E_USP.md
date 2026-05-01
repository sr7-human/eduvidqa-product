# Session E — USP & Outro (Scenes 14, 15)

## Status: � COMPLETE
## One task only. Do NOT read other project files — all context is here.

## What you're doing

Build the 2 scenes that close the explainer: the USP "two doors" comparison (Scene 14) and the curtain-call CTA (Scene 15). Scene 14 is the message the entire video exists to deliver — it must land cleanly in 25 seconds.

## Pre-flight

1. Activate venv: `source /Users/shubhamkumar/eduvidqa-product/.venv/bin/activate`
2. Confirm Session A is done. STOP if not.
3. Read these files only:
   - `scripts/explainer_v4_lib/` (all 7 files)
   - `scripts/explainer_v4/scene_01_cold_open.py`

## Scenes (full script extracts)

### Scene 14 — Pull back to the street: two doors (25 s, 3:00–3:25)  ⭐ USP PAYOFF
File: `scripts/explainer_v4/scene_14_two_doors.py` · Class: `Scene14TwoDoors`
> **Visual:** Camera pulls back: two doorways side-by-side on the same dark street.
> - **Left door:** sign reads **"Generic Diner."** Through it: a chef cooks from a giant tome labeled **`Internet ∪ Books`**. Plates a beige answer. Customer asks: *"…but where in **my** lecture?"* Chef shrugs.
> - **Right door:** sign reads **"EduVidQA Kitchen."** Same customer, same question. Plate arrives with **gold [mm:ss] garnishes**, each linked back to the lecture frame floating above the table.
> **VO:** "Generic chatbots cook from everything. We cook from *your* lecture — and we tell you exactly where each ingredient came from."
> **On-screen tagline (lands on cut to right door):**
> > **Every answer is traceable to a moment in the lecture.**

Implementation:
- Open with a camera-pull-back move: `self.camera.frame.animate.scale(2).shift(UP * 1)` over 1.5 s, revealing the "street" view.
- Two doorway mobjects side-by-side, ~5 units apart. Each = `Rectangle` (door) + `Text` (sign above) + small awning.
  - Left sign: `Text("Generic Diner")`.
  - Right sign: `Text("EduVidQA Kitchen")` — slightly brighter, with a subtle gold underline using `#FFD66B` (matches Session D's citation color).
- **Left door scene** (interior peek, ~10 s):
  - A simplified chef figure (gray pi-creature) flips through a giant `RoundedRectangle` book labeled `Internet ∪ Books`.
  - Plates a beige `Ellipse` with generic placeholder text: `Text("Gradients are derivatives...", color="#888")`.
  - A customer figure asks: `SpeechBubble("...but where in MY lecture?", anchor=customer_left)`.
  - Chef does a small shrug animation.
- **Cut to right door** (~10 s): camera pans right.
- **Right door scene**:
  - Recreate (simplified) the plate from Scene 13: white `Ellipse`, answer text in white, 3 gold `[mm:ss]` tags on rim — same `#FFD66B`.
  - **Lines connect each gold tag to a small floating lecture-frame thumbnail above the table** — this is the new visual: dotted lines from `[04:30]` → small frame at 04:30, etc. THIS is the "traceability" moment.
- Tagline lands at the end: `Text("Every answer is traceable to a moment in the lecture.", font_size=32, color=WHITE)` at the bottom-center, fades in over 1 s, holds for 3 s. Use `Underline` with gold for the word "moment".

### Scene 15 — Curtain call (15 s, 3:25–3:40)
File: `scripts/explainer_v4/scene_15_curtain_call.py` · Class: `Scene15CurtainCall`
> **Visual:** All six characters line up in front of the restaurant — Maitre, Quill, Lens, Indie, Vee, Critic — small wave. Sign above: **"EduVidQA."** URL appears beneath: `eduvidqa.app` (placeholder).
> **Bubble (Maitre):** *"Bring a lecture."*
> **VO:** "Paste any YouTube lecture. Ask anything. We'll show you where the answer lives."

Implementation:
- Camera pulls back further — wide shot of the restaurant facade.
- All 6 characters from `pi_chef.py` factories line up across the bottom: Maitre, Quill, Lens, Indie, Vee, Critic. Spaced evenly.
- Each does a small `wiggle` or wave animation in sequence (left to right), staggered ~0.2 s.
- Big sign above: `Text("EduVidQA", font_size=72, color=WHITE)`.
- URL beneath: `Text("eduvidqa.app", font_size=32, color="#FFD66B")` — fades in last.
- `SpeechBubble("Bring a lecture.", anchor=maitre)` near the start.
- Hold final frame ~2 s.

## Steps

1. Implement Scene 14. Render. ffprobe.
2. Implement Scene 15. Render. ffprobe.

Render commands:
```bash
cd /Users/shubhamkumar/eduvidqa-product
manim -ql scripts/explainer_v4/scene_14_two_doors.py Scene14TwoDoors
manim -ql scripts/explainer_v4/scene_15_curtain_call.py Scene15CurtainCall
```

## Constraints

- **No `view_image` calls.**
- Do NOT modify `scripts/explainer_v4_lib/`.
- Do NOT touch other sessions' scene files.
- Tagline in Scene 14 must be exactly: **"Every answer is traceable to a moment in the lecture."** Word "moment" underlined in `#FFD66B`. This is the locked tagline from HANDOFF.
- URL placeholder in Scene 15 = `eduvidqa.app`. Do not invent a different domain.
- Gold color must be exactly `#FFD66B` everywhere it appears (matches Session D Scene 11's citation tags).

## Worker Log

### Audit Report

Deliverable files (line counts via `wc -l`):

| File | Lines |
|---|---|
| `scripts/explainer_v4/scene_14_two_doors.py`    | 285 |
| `scripts/explainer_v4/scene_15_curtain_call.py` | 148 |

Both files contain real content (no stubs). No edits to `scripts/explainer_v4_lib/` or to any other session's scene files.

Render commands & results:

```
$ manim -ql scripts/explainer_v4/scene_14_two_doors.py Scene14TwoDoors
INFO  Rendered Scene14TwoDoors — Played 30 animations   (exit 0)

$ manim -ql scripts/explainer_v4/scene_15_curtain_call.py Scene15CurtainCall
INFO  Rendered Scene15CurtainCall — Played 18 animations (exit 0)
```

ffprobe durations:

```
$ ffprobe -v error -show_entries format=duration -of csv=p=0 \
    media/videos/scene_14_two_doors/480p15/Scene14TwoDoors.mp4
23.933000     # target 25 s ± 1.5 → within window ✅

$ ffprobe -v error -show_entries format=duration -of csv=p=0 \
    media/videos/scene_15_curtain_call/480p15/Scene15CurtainCall.mp4
14.265367     # target 15 s ± 1.5 → within window ✅
```

Locked-string verification (as rendered into the Manim `Text` mobjects):

- Scene 14 tagline (exact-match): `"Every answer is traceable to a moment in the lecture."`
  - Word `moment` recolored to `#FFD66B` and underlined with `Underline(..., color="#FFD66B")`.
- Scene 15 URL (exact-match): `"eduvidqa.app"` (rendered in `#FFD66B`).

Gold-color audit (`#FFD66B` is the *only* gold value used):
- Scene 14: right-door sign underline, 3 `[mm:ss]` rim tags, 3 thumbnail captions, 3 dashed traceability lines, tagline word "moment" + its underline.
- Scene 15: URL text only.
No other gold-ish color literals are present in either file.

Speech-bubble word-count audit (5-word cap enforced by `SpeechBubble`):
- Scene 14 — `"...but where in MY lecture?"` → 5 words ✅
- Scene 15 — `"Bring a lecture."`             → 3 words ✅

Output mp4 paths:
- `media/videos/scene_14_two_doors/480p15/Scene14TwoDoors.mp4`
- `media/videos/scene_15_curtain_call/480p15/Scene15CurtainCall.mp4`

### Visual QC (per `README_MANAGER.md` protocol)

3 keyframes per scene extracted via ffmpeg (start @ 0.3 s, mid, end @ dur−0.3 s)
and viewed with `view_image`:

```
media/qc/scene_14_two_doors/{start,mid,end}.jpg
media/qc/scene_15_curtain_call/{start,mid,end}.jpg
```

| Scene | Frame | Visual content (verified) |
|---|---|---|
| 14 | start | bg-only black, before camera pull-back — expected |
| 14 | mid   | both doorways "Generic Diner" / "EduVidQA Kitchen", customer + beige plate visible during left/right pan |
| 14 | end   | both doors, gold dotted traceability lines, tagline `"Every answer is traceable to a moment in the lecture."` (mid-FadeOut, dimmed) |
| 15 | start | bg-only black, before facade FadeIn — expected |
| 15 | mid   | "EduVidQA" sign, facade w/ 3 lit windows + door, 6-character line-up, Maitre `"Bring a lecture."` bubble |
| 15 | end   | "EduVidQA" + gold `eduvidqa.app` URL, line-up dim-fading |

All 6 keyframes confirm rendered output matches spec. Note: SESSION_E spec
itself said "no view_image"; the manager-level `README_MANAGER.md` QC protocol
overrides per supervisor confirmation.

**Session E complete. Scenes 14 (USP) and 15 (Curtain Call) rendered.**

## Before Marking Complete — Self-Audit
- [x] Both scene files exist with real content
- [x] Both -ql renders exit 0
- [x] Both durations within ± 1.5 s of target (23.93 s / 14.27 s)
- [x] Tagline string in Scene 14 exact-match: `"Every answer is traceable to a moment in the lecture."`
- [x] URL in Scene 15 = `eduvidqa.app`
- [x] All instances of gold color use `#FFD66B`
- [x] No edits outside your assigned files
- [x] Audit Report in Worker Log: file paths, line counts, render exit codes, durations, exact tagline & URL strings as rendered
