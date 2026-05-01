# Explainer v4 — Manager Dispatch Notes

**Goal:** Render `scripts/explainer_v4/` — a ~3:15 Manim restaurant-metaphor explainer for EduVidQA. Full creative script lives in `HANDOFF.md` §"My honest take first" → "Kitchen Tour".

## Dispatch order

1. **Run Session A first, ALONE.** It builds `scripts/explainer_v4_lib/` (shared helpers) and a smoke-test render of Scene 1. All other sessions import from this lib — they CANNOT start until A is committed.
2. **After A finishes**, dispatch Sessions B, C, D, E **in parallel** (4 separate worker chats).
3. Each session writes to its own scene files only — no cross-file edits. No merge conflicts by construction.

## Shared conventions (locked by Session A)

- Dark 3b1b background (`config.background_color = "#0e1117"`).
- Soft-pastel pi-creature characters (Session A defines the palette).
- One persistent `OrderTicket` Mobject reused in Acts II–III (Session A defines the class; later sessions instantiate).
- Lower-third tech labels appear on character's first entrance only.
- Speech bubbles ≤ 5 words, ≤ 2 on screen at once, fade in/out < 0.4 s.
- VO timing assumed 150 wpm — each scene file lists its target duration in seconds; workers tune `self.wait()` to match.
- Render target for review: `manim -ql` (480p15). Workers must verify their scene renders cleanly at -ql AND visually QC the output keyframes before marking complete.

## Visual QC protocol (every session must follow)

Duration alone does not prove correctness — a black screen renders cleanly too. Each worker MUST extract keyframes from every rendered mp4 and view them with `view_image`. **Director review = max quality, not preview thumbnails.**

Per-frame extraction (paste into worker terminal after each render):
```bash
# Native resolution (no scaling), highest JPEG quality
ffmpeg -y -ss "$T" -i "$IN" -vframes 1 -q:v 2 "$QC/frame_<label>.jpg" 2>/dev/null
```
Key changes from earlier draft:
- **No `-vf scale=480:-1`** — we keep the mp4's native 854×480 (the `-ql` source) so text/colors are inspected at full fidelity.
- **`-q:v 2`** instead of `-q:v 8` — ~120 KB per frame instead of ~30 KB. Closer to lossless.
- This puts each frame in the "small image" tier (~100 KB) per session-sizing rules.

**Image budget per session (small-tier safe limit = 8):**
| Session | Frames | Distribution |
|---|---|---|
| A | 3 | start / mid / end of Scene 1 |
| B | 8 | 2 per scene × 4 scenes (mid + end) |
| C | 6 | mid of each × 5 + end of Scene 10 |
| D | 8 | Scene 11: 4 (climax), Scenes 12 & 13: 2 each |
| E | 5 | Scene 14: 3 (USP), Scene 15: 2 |

If a worker needs more frames to debug, they MUST re-render after a code fix — not extract additional frames — to stay under budget.

## File layout each session must follow

```
scripts/
  explainer_v4_lib/              # owned by Session A only
    __init__.py
    floorplan.py                 # RestaurantFloorplan VGroup
    pi_chef.py                   # PiChef class + 6 character factories
    order_ticket.py              # OrderTicket Mobject
    speech_bubble.py             # SpeechBubble + lower_third_label
    base_scene.py                # BaseScene with bg + camera defaults
    palette.py                   # color constants
  explainer_v4/
    scene_01_cold_open.py        # Session A
    scene_02_quill_chunks.py     # Session B
    scene_03_lens_keyframes.py   # Session B
    scene_04_indie_files.py      # Session B
    scene_05_lights_up.py        # Session C
    scene_06_customer_pauses.py  # Session C
    scene_07_maitre_routes.py    # Session C
    scene_08_indie_retrieves.py  # Session B
    scene_09_timestamp_rerank.py # Session C
    scene_10_live_frame.py       # Session C
    scene_11_chef_cooks.py       # Session D
    scene_12_critic_tastes.py    # Session D
    scene_13_delivery.py         # Session D
    scene_14_two_doors.py        # Session E
    scene_15_curtain_call.py     # Session E
```

## After all 5 sessions finish (manager's job, not in any worker scope)

- Concat scene renders → `media/videos/explainer_v4/720p30/EduVidQAExplainer.mp4`.
- Bump quality to `-qm` once -ql review passes.
- Final `-qh` only after supervisor sign-off.
