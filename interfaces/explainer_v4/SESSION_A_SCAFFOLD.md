# Session A — Scaffolding + Scene 1 (Cold Open)

## Status: � COMPLETE
## ⚠ MUST RUN BEFORE B/C/D/E. They block on your output.
## One task only. Do NOT read other project files — all context is here.

## What you're doing

Build the shared Manim helper library that all 15 scenes of the EduVidQA "Kitchen Tour" explainer will import. Then prove it works by rendering **Scene 1 (Cold Open, ~8 s)** end-to-end.

The explainer is a restaurant metaphor for a multimodal RAG pipeline. Six characters (Maitre, Quill, Lens, Indie, Chef Vee, Critic) work across a continuous floorplan: pantry (left) → vector library (center) → kitchen (right) → dining table (front).

## Visual conventions (locked — do not deviate)

- **Background:** dark, `#0e1117` (3b1b style). Set via `config.background_color`.
- **Characters:** soft-pastel pi-creature variants. Use Manim's built-in `PiCreature` if available via `manim_pi_creatures` / `manimce-pi-creatures`; otherwise approximate with `VGroup` of `Circle` (body) + 2 `Dot`s (eyes) + small `Arc` (mouth). Pick whichever gets you a working render fastest.
- **Palette (soft pastel on dark bg):**
  - Maitre (waiter): `#A8E6A1` (mint)
  - Quill (scribe): `#A8C8FF` (sky)
  - Lens (photographer): `#FFC58A` (peach)
  - Indie (librarian): `#D7B3FF` (lavender)
  - Chef Vee: `#FF9B9B` (coral)
  - Critic: `#F0F0F0` (off-white)
  - Customer (You): `#FFE066` (butter)
- **Floorplan coords (camera frame 14×8 units):**
  - Pantry: x ∈ [-6, -2.5], floor y = -2.5
  - Library wall: x ∈ [-2.5, 1.5]
  - Kitchen counter: x ∈ [1.5, 5]
  - Dining table: bottom-front, centered ~ (0, -3)

## Deliverables (exact paths)

1. `scripts/explainer_v4_lib/__init__.py` — re-exports.
2. `scripts/explainer_v4_lib/palette.py` — color constants from list above.
3. `scripts/explainer_v4_lib/floorplan.py` — `RestaurantFloorplan` VGroup with named sub-positions: `.pantry`, `.library`, `.kitchen`, `.table` (each is a `Point` / coords tuple). Render = thin outlined zones with subtle floor line; no labels.
4. `scripts/explainer_v4_lib/pi_chef.py` — `PiChef(name, color, label_text)` class returning a VGroup. Methods: `.walk_to(point, run_time)`, `.hold_prop(mobject)`, `.set_expression("neutral"|"thinking"|"happy")`. Plus 6 factory functions: `make_maitre()`, `make_quill()`, `make_lens()`, `make_indie()`, `make_vee()`, `make_critic()`, `make_customer()`. Each factory bakes in color + label.
5. `scripts/explainer_v4_lib/order_ticket.py` — `OrderTicket(question, timestamp, video_id)` Mobject: small white card (1.6 × 1.0 units) with 3 lines of text. Methods: `.update_question(new_text)`, `.staple_to(mobject)` (animation helper).
6. `scripts/explainer_v4_lib/speech_bubble.py` —
   - `SpeechBubble(text, anchor, side="right")` — auto-positions next to anchor, ≤ 5-word enforcement raises `ValueError` if violated. Includes `.show(scene, duration=1.0)` that fades in/out within 0.4 s.
   - `lower_third_label(character, label_text)` — animation that slides a small caption across the bottom-left for 2 s then exits. Used on character's first entrance.
7. `scripts/explainer_v4_lib/base_scene.py` — `BaseScene(MovingCameraScene)` setting bg + standard camera frame. All scene files inherit from it.
8. `scripts/explainer_v4/scene_01_cold_open.py` — implements **Scene 1** below. Class name: `Scene01ColdOpen`.

## Scene 1 — Cold Open (target duration 8 s)

Script extract:

> **Visual:** Pitch black. A neon sign flickers on, top-center: **"EduVidQA — Open Kitchen."** The kitchen floorplan dim-lit behind it. A small delivery truck rolls in from screen-left and drops a film canister labeled `lecture.mp4` at the back door. Sign brightens.
> **VO (8 s):** "Most AI tutors answer from a textbook they read once, somewhere. *Ours* prepares the lecture itself — before you ever ask."

Implementation notes:
- Start with bg only. `wait(0.3)`.
- Neon sign: `Text("EduVidQA — Open Kitchen", color="#FF6B9D")` with a `Flash` or `flicker` animation (3 quick opacity blinks then full).
- Floorplan fades in at 30% opacity behind the sign (use `RestaurantFloorplan().set_opacity(0.3)`).
- Truck: simple `Rectangle` + 2 `Circle` wheels, slides in from `LEFT * 8` to `LEFT * 2.5`, drops a small `RoundedRectangle` labeled `lecture.mp4`, exits screen-right.
- Sign brightens from 60% → 100% opacity at the end.
- Total runtime: tune `self.wait()` to land at 8.0 s ± 0.5 s.

## Steps

1. Activate venv: `source /Users/shubhamkumar/eduvidqa-product/.venv/bin/activate`. Verify `manim --version` works (already installed for v3).
2. Create the 8 deliverable files above. Keep each file under 150 lines — this is scaffolding, not features.
3. Render the smoke test:
   ```bash
   cd /Users/shubhamkumar/eduvidqa-product
   manim -ql scripts/explainer_v4/scene_01_cold_open.py Scene01ColdOpen
   ```
4. Confirm output mp4 exists at `media/videos/scene_01_cold_open/480p15/Scene01ColdOpen.mp4` and is 7–9 s long (`ffprobe -v error -show_entries format=duration -of csv=p=0 <path>`).
5. If render fails, fix and re-run. Do not mark complete until it renders cleanly.

## Constraints

- **No `view_image` calls.** Verify renders by running `ffprobe` for duration only.
- Do NOT touch any file outside `scripts/explainer_v4_lib/` and `scripts/explainer_v4/scene_01_cold_open.py`.
- Do NOT modify `requirements.txt` unless `manim` itself is missing (it's already installed — v3 used it).
- Keep imports minimal — no `numpy` tricks unless strictly necessary.

## Worker Log

### Audit Report

Deliverable files (line counts via `wc -l`):

| File | Lines |
|---|---|
| `scripts/explainer_v4_lib/__init__.py` | 53 |
| `scripts/explainer_v4_lib/palette.py` | 17 |
| `scripts/explainer_v4_lib/floorplan.py` | 52 |
| `scripts/explainer_v4_lib/pi_chef.py` | 100 |
| `scripts/explainer_v4_lib/order_ticket.py` | 63 |
| `scripts/explainer_v4_lib/speech_bubble.py` | 86 |
| `scripts/explainer_v4_lib/base_scene.py` | 18 |
| `scripts/explainer_v4/scene_01_cold_open.py` | 125 |

All 8 deliverables present, all under 150 lines, no stubs.

Render command:
```
manim -ql scripts/explainer_v4/scene_01_cold_open.py Scene01ColdOpen
```
Exit code: 0. Played 15 animations. File ready at:
`media/videos/scene_01_cold_open/480p15/Scene01ColdOpen.mp4`

ffprobe duration:
```
$ ffprobe -v error -show_entries format=duration -of csv=p=0 \
    media/videos/scene_01_cold_open/480p15/Scene01ColdOpen.mp4
7.533000
```
Within 7–9 s window ✅.

Imports: lib only depends on `manim` + `numpy` (stdlib otherwise). No circular imports — `__init__` is the only cross-module import surface, and each submodule only pulls from `palette`. Scene file imports via the `explainer_v4_lib` package only.

**Session A complete. `explainer_v4_lib/` is ready. B/C/D/E unblocked.**

## Before Marking Complete — Self-Audit
- [ ] All 8 deliverable files exist and have real content (not stubs)
- [ ] `manim -ql scripts/explainer_v4/scene_01_cold_open.py Scene01ColdOpen` exits 0
- [ ] Output mp4 exists and is 7–9 s duration (paste `ffprobe` output in log)
- [ ] No imports from outside the workspace; lib has no circular imports
- [ ] Audit Report written in Worker Log: list each deliverable file with line count, paste the ffprobe duration, and confirm the smoke-test mp4 path

## Handoff to B/C/D/E
After your audit passes, post in the manager chat: **"Session A complete. `explainer_v4_lib/` is ready. B/C/D/E unblocked."**
