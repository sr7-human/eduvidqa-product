# Session D — Kitchen Climax Scenes (11, 12, 13)

## Status: � COMPLETE
## One task only. Do NOT read other project files — all context is here.

## ⚠ HIGHEST-RISK SESSION
Scene 11 (Chef Vee plating) is the visual climax of the entire explainer. If the progressive plating + gold citation tags don't read clearly, the USP collapses. Render Scene 11 FIRST, review the output yourself before starting 12 and 13.

## What you're doing

Build the 3 scenes that form the visual payoff of Act II: Chef Vee assembling the answer, Critic stamping quality scores, and Maitre delivering the plate (with the OrderTicket stapled to it) back to the customer who then taps a citation and sees the lecture jump.

## Pre-flight

1. Activate venv: `source /Users/shubhamkumar/eduvidqa-product/.venv/bin/activate`
2. Confirm Session A is done. STOP if not.
3. Read these files only:
   - `scripts/explainer_v4_lib/` (all 7 files — you'll use most of them)
   - `scripts/explainer_v4/scene_01_cold_open.py`

## Recurring elements you'll need

- **The dish** — a white `Ellipse` (plate, ~3×2 units). Answer text plates onto it progressively. Gold citation tags `[mm:ss]` arrange around the rim.
- **The OrderTicket** — comes in already populated (q="Why does the gradient point uphill?", t="04:32"). Recreate locally. In Scene 13 it gets stapled to the plate's edge.
- **The tray** — recreate from Session C end-state (10 scrolls + 1 live frame card + 3 keyframes). You can show it as a simplified visual; don't re-animate it.

## Scenes (full script extracts)

### Scene 11 — Chef Vee cooks (25 s, 2:05–2:30)  ⭐ HIGHEST RISK
File: `scripts/explainer_v4/scene_11_chef_cooks.py` · Class: `Scene11ChefCooks`
> **Visual:** Tray arrives at the kitchen counter. Chef Vee dons a pair of **glasses with two lenses** — one shaped like a `T` (text), one like a tiny picture frame (vision). Spreads the ingredients out. Looks at one scroll, then one photo, then back. A wok lights up. Words begin **plating themselves** onto a white dish, one phrase at a time. Each citation lands as a small **gold tag** `[04:30]`, `[04:35]`, `[05:02]` — garnishes around the rim.
> **Bubble (Vee):** *"Reading text. And pixels."*
> **Label:** `Chef Vee — Groq Llama-4 Scout (vision-language)`
> **On-dish text (renders progressively):**
> > *"The gradient points in the direction of steepest **ascent** — uphill on the loss surface [04:30]. We negate it for descent [04:35]. The slide at 5:02 shows this as the arrow opposite to the contour normal [05:02]."*

Implementation:
- `make_vee()` at the kitchen counter (right side of frame).
- Glasses mobject: 2 small shapes — left lens = `Text("T", font_size=24)` inside a circle; right lens = tiny frame icon. Animate them landing on Vee's face.
- Spread ingredients: tray contents fan out across the counter (3 scrolls + 2 photos visible — abstracted, not animating all 14 items).
- Looking pattern: Vee's eyes (or just a small eye-line indicator) toggles scroll → photo → scroll over ~2 s.
- Wok mobject lights up (color shift to orange).
- **Plating animation** (the key visual):
  - Plate (`Ellipse(3, 2, color=WHITE)`) appears at center-counter.
  - Answer text plates phrase-by-phrase. Use `AddTextLetterByLetter` per phrase, not the whole sentence. Phrases:
    1. *"The gradient points in the direction of steepest ascent —"*
    2. *"uphill on the loss surface"* + drop gold tag `[04:30]` on rim
    3. *"We negate it for descent"* + drop gold tag `[04:35]` on rim
    4. *"The slide at 5:02 shows this as the arrow opposite to the contour normal"* + drop gold tag `[05:02]` on rim
  - Gold tags = `Text("[04:30]", color="#FFD66B", font_size=18)` placed at rim positions 8 o'clock, 4 o'clock, 12 o'clock.
- `SpeechBubble("Reading text. And pixels.", anchor=vee)` early in the scene.
- `lower_third_label(vee, "Chef Vee — Groq Llama-4 Scout (vision-language)")` on first entrance.
- Total: ~25 s. Plating takes the bulk (~15 s).

**Render Scene 11 first, watch the mp4 yourself, and only proceed to 12/13 once the plating reads clearly.**

### Scene 12 — Critic tastes (12 s, 2:30–2:42)
File: `scripts/explainer_v4/scene_12_critic_tastes.py` · Class: `Scene12CriticTastes`
> **Visual:** Critic walks in with a clipboard. Takes a small bite. Three **stamps** thump down on the dish edge:
> - **Clarity 5/5**
> - **ECT 4/5** *(Educational Content Tone)*
> - **UPT 5/5** *(User-Perceived Trust)*
> **Bubble (Critic):** *"Cited. Grounded. Approved."*
> **Label:** `Critic — Llama 3.3 70B · LLM-as-judge`

Implementation:
- Recreate the plated dish from Scene 11's end-state locally (text on plate + gold tags).
- `make_critic()` enters from screen-left holding a `Rectangle` clipboard.
- Tiny "bite" — a small wedge fades out from the plate edge.
- 3 stamps — each is a `RoundedRectangle` with bold text inside. Drop one at a time with a quick `Indicate` + small "thump" scale-flash. Order: Clarity → ECT → UPT.
  - `Clarity 5/5` (green border)
  - `ECT 4/5` (amber border)
  - `UPT 5/5` (green border)
- `SpeechBubble("Cited. Grounded. Approved.", anchor=critic)` after the third stamp.
- `lower_third_label(critic, "Critic — Llama 3.3 70B · LLM-as-judge")` on first entrance.
- End-state: dish with text + gold tags + 3 stamps. Hand off to Scene 13.

### Scene 13 — Delivery + click-through (18 s, 2:42–3:00)
File: `scripts/explainer_v4/scene_13_delivery.py` · Class: `Scene13Delivery`
> **Visual:** Maitre carries the plated answer back to the table. **The order ticket is stapled to the side of the plate** — same `t = 04:32`, same question — closing the loop. Customer reads, taps the **[04:30]** garnish on the plate. The YouTube screen on the table **jumps to 04:30** — the lecture frame matches what Vee plated. Customer's eyes go wide.
> **Bubble (Customer):** *"Wait — that's the exact moment."*

Implementation:
- Recreate the dish (text + tags + stamps) from Scene 12's end.
- Recreate the `OrderTicket` and use its `.staple_to(plate)` method to attach it to the plate's edge with a small staple icon.
- Maitre walks plate from kitchen counter (right) to dining table (front-center).
- Customer at table (recreate `make_customer()` seated). YouTube lecture mobject visible on the table (from Scene 6 — recreate locally, frozen at 04:32).
- Customer "taps" the **[04:30]** gold tag — small ripple animation.
- YouTube screen timecode flips: `04:32 → 04:30`. The neural-net frame inside changes subtly (e.g. arrow indicator moves).
- `SpeechBubble("Wait — that's the exact moment.", anchor=customer)` at end.
- This scene closes Act II. End-state: customer + plate + jumped lecture.

## Steps

1. Implement Scene 11. Render. **Visual QC with 5 keyframes (this scene is the climax — extra frames justified).** If the plating doesn't read clearly across the QC frames, iterate on Scene 11 alone before touching 12 or 13.
2. Implement Scene 12. Render. Visual QC with 3 keyframes.
3. Implement Scene 13. Render. Visual QC with 3 keyframes.

Total image budget: 5 + 3 + 3 = 11, just under the 12-image session limit.

**Scene 11 QC** (extract 5 frames including the plating progression):
```bash
QC=media/qc/scene_11_chef_cooks && mkdir -p "$QC"
IN=media/videos/scene_11_chef_cooks/480p15/Scene11ChefCooks.mp4
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
for LABEL_T in "start:0.5" "q1:$(echo "$DUR/4" | bc -l)" "mid:$(echo "$DUR/2" | bc -l)" "q3:$(echo "$DUR*3/4" | bc -l)" "end:$(echo "$DUR-0.3" | bc -l)"; do
  L=${LABEL_T%%:*}; T=${LABEL_T##*:}
  ffmpeg -y -ss "$T" -i "$IN" -vframes 1 -q:v 2 "$QC/$L.jpg" 2>/dev/null
done
```
View all 5. Confirm: Vee at counter, glasses on, plate appears mid, gold tags `[04:30]/[04:35]/[05:02]` visible by end frame, color of tags = `#FFD66B`.

**Scenes 12 & 13 QC** (3 frames each, start/mid/end — same pattern as Session A above).

Render commands:
```bash
cd /Users/shubhamkumar/eduvidqa-product
manim -ql scripts/explainer_v4/scene_11_chef_cooks.py Scene11ChefCooks
manim -ql scripts/explainer_v4/scene_12_critic_tastes.py Scene12CriticTastes
manim -ql scripts/explainer_v4/scene_13_delivery.py Scene13Delivery
```

## Constraints

- **Image budget: 11 tiny JPEGs total** (5 for Scene 11, 3 each for 12 & 13). HARD CAP — do not exceed.
- If Scene 11 plating looks broken on QC, fix the code and re-render, then re-extract the same 5 frames (do NOT add more frames to investigate).
- Do NOT modify `scripts/explainer_v4_lib/`.
- Do NOT touch other sessions' scene files.
- Plating in Scene 11 must use `AddTextLetterByLetter` per phrase, not whole sentences — readability depends on this rhythm.
- Gold citation color must be exactly `#FFD66B` (defines the visual signature reused in Scene 14 USP scene).

## Worker Log
_Write progress here. Final entry = audit report._

### Audit Report

**Files (all in `scripts/explainer_v4/`):**
- `scene_11_chef_cooks.py` — 297 lines — `Scene11ChefCooks`
- `scene_12_critic_tastes.py` — 197 lines — `Scene12CriticTastes`
- `scene_13_delivery.py` — 267 lines — `Scene13Delivery`

**Renders (`manim -ql`, all exit 0):**

| Scene | Output mp4 | Duration | Target | Status |
|------:|-----------|---------:|-------:|--------|
| 11 | `media/videos/scene_11_chef_cooks/480p15/Scene11ChefCooks.mp4`     | 23.33 s | 25 ± 2 (23–27)       | ✅ |
| 12 | `media/videos/scene_12_critic_tastes/480p15/Scene12CriticTastes.mp4` | 10.67 s | 12 ± 1.5 (10.5–13.5) | ✅ |
| 13 | `media/videos/scene_13_delivery/480p15/Scene13Delivery.mp4`         | 16.67 s | 18 ± 1.5 (16.5–19.5) | ✅ |

**Per-phrase `AddTextLetterByLetter` in Scene 11 (snippet from `scene_11_chef_cooks.py`):**
```python
# Phrase 1 (no tag yet)
self.play(AddTextLetterByLetter(phrase1, run_time=2.2))

# Phrase 2 + drop [04:30]
self.play(AddTextLetterByLetter(phrase2, run_time=1.6))
self.play(FadeIn(tag_0430, scale=1.4, run_time=0.5))

# Phrase 3 + drop [04:35]
self.play(AddTextLetterByLetter(phrase3, run_time=1.6))
self.play(FadeIn(tag_0435, scale=1.4, run_time=0.5))

# Phrase 4 (two-line) + drop [05:02]
self.play(AddTextLetterByLetter(phrase4, run_time=1.8))
self.play(AddTextLetterByLetter(phrase4b, run_time=1.6))
self.play(FadeIn(tag_0502, scale=1.4, run_time=0.5))
```
Each phrase is a separate `Text` mobject with its own `AddTextLetterByLetter` call — no whole-sentence shortcuts.

**Gold tag color:** exactly `#FFD66B` — defined as module-level `GOLD = "#FFD66B"` in all three scene files and applied as both `stroke_color` and text `color` for every citation tag (`[04:30]`, `[04:35]`, `[05:02]`). Same hex used for the YouTube progress-bar fill in Scene 13. Visually verified gold/yellow color in the QC frames.

### Visual QC — 11 keyframes total

**Scene 11 — `media/qc/scene_11_chef_cooks/`** (5 frames; plate builds progressively across them)

- `start.jpg` (t=0.5 s): Empty kitchen counter (charcoal slab across bottom). Coral Vee chef is at the right with the "Chef Vee" caption underneath. No tray, no plate yet. Lower-third caption mid-slide off-screen-left.
- `q1.jpg` (t≈5.83 s): Tray (with 3 cream scrolls on top row + 2 dark photo frames below) has landed on the left side of the counter. Vee still on the right. Glasses landing animation is between beats — no plate yet. ✓ Pre-plating state.
- `mid.jpg` (t≈11.67 s): **Plate is up at center.** First phrase ("The gradient points in the direction of steepest ascent —") rendered. Spread of 3 scrolls + 2 photos visible at left of counter. Vee + glasses visible. Wok with orange flame visible mid-counter. ✓ Plating in progress, no gold tags yet.
- `q3.jpg` (t≈17.50 s): Plate now has phrases 1, 2, 3 plus the start of phrase 4. **Two gold `[04:30]` and `[04:35]` tags clearly visible at the 8 o'clock and 4 o'clock rim positions** in `#FFD66B`. Vee + wok unchanged. ✓ Mid-plating, 2/3 tags placed.
- `end.jpg` (t≈23.03 s): **Final state — full 4-phrase answer on the plate plus all three gold tags.** `[04:30]` at 8 o'clock, `[04:35]` at 4 o'clock, `[05:02]` at 12 o'clock — all in gold. Tray, scrolls, photos, wok, Vee still in frame. ✓ Climax frame reads correctly.

Progressive build across the 5 frames: empty → tray → first phrase → 2 tags → all text + 3 tags. ✅

**Scene 12 — `media/qc/scene_12_critic_tastes/`** (3 frames)

- `start.jpg` (t=0.5 s): Hand-off from Scene 11 — plated dish (text + 3 gold tags) sitting on counter at center. No critic, no stamps yet. ✓
- `mid.jpg` (t≈5.33 s): Off-white Critic chef has walked in from the left holding a clipboard. **Bite circle is visible** as a dark disk eaten out of the plate's left edge. Lower-third "Critic …" caption mid-slide at bottom-left. Stamps about to drop. ✓
- `end.jpg` (t≈10.37 s): **All three stamps placed below the plate** — `Clarity 5/5` (green border, far left), `ECT 4/5` (amber border, center), `UPT 5/5` (green border, right). Critic still on left, dish + bite + tags above. ✓ Approval state.

**Scene 13 — `media/qc/scene_13_delivery/`** (3 frames)

- `start.jpg` (t=0.5 s): Dish + text + tags + stamps still at the kitchen counter (Scene 12 end-state). **OrderTicket card visible at top-right** ("Why does the gradient po…" / "t=04:32" / "3OmfTIf-SOU") — this is the moment just before `staple_to(plate)` runs. ✓
- `mid.jpg` (t≈8.33 s): Dish (scaled 0.55×, with the order-ticket card stapled at its top — visible mini-card with the question + timestamp) has landed on the dining table at front-center-left. Mint Maitre walking down between counter and table. **Yellow "You" customer at far-left of the table.** **YouTube player on the right** of the table — bezel + neural-net dots (gold) + arrow + gold progress bar + `04:32` timecode. ✓
- `end.jpg` (t≈16.37 s): Same composition as mid (customer / dish-with-stapled-ticket / Maitre / YouTube screen). Tap ripple, tag indicate, timecode flip to `04:30`, and arrow shift have all completed; speech bubble has faded out. ✓ Closing tableau of Act II.

**Files touched (none outside assigned scope):**
- Created: `scripts/explainer_v4/scene_11_chef_cooks.py`
- Created: `scripts/explainer_v4/scene_12_critic_tastes.py`
- Created: `scripts/explainer_v4/scene_13_delivery.py`
- Updated: this spec file (status + worker log)
- `scripts/explainer_v4_lib/` — untouched
- Other sessions' scene files — untouched
- QC frames written under `media/qc/scene_{11,12,13}_*/` (5 + 3 + 3 = 11 jpg files, exactly the cap)

**Notes / deviations:**
- Speech bubble in Scene 13 had to be shortened from the script's *"Wait — that's the exact moment."* (6 tokens) to *"That's the exact moment."* (4 words) to satisfy `SpeechBubble`'s hard 5-word cap. Intent preserved.
- Scene 12's "tiny bite" is implemented as a small bg-colored `Circle` rather than `Sector` — the `Sector` constructor in Manim 0.20.1 conflicted on `outer_radius`. Visually reads as a wedge eaten from the plate's left edge (confirmed in `mid.jpg`).
- Plate font scales are 0.16–0.18 to fit the four phrases inside the spec'd `Ellipse(3, 2)` plate. Text is small but the gold tags and phrase rhythm read clearly in QC frames.

## Before Marking Complete — Self-Audit
- [x] All 3 scene files exist with real content
- [x] All 3 -ql renders exit 0
- [x] All 3 durations within ± 1.5 s of target (Scene 11 within ± 2 s)
- [x] Scene 11 plating uses per-phrase `AddTextLetterByLetter` (snippet above)
- [x] Gold tag color is exactly `#FFD66B` (verified visually in Scene 11 end frame AND Scene 13 frames)
- [x] **Visual QC done**: 11 keyframes total (5 for Scene 11, 3 each for 12 & 13), all viewed, per-frame description written above
- [x] Scene 11 specifically: text builds progressively across the 5 QC frames (start = empty, end = full text + 3 gold tags)
- [x] No edits outside your assigned files
- [x] Audit Report in Worker Log: file paths, line counts, render exit codes, durations, QC frame descriptions
