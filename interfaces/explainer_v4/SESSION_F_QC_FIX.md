# Session F — Full-Cut QC & Defect Fixing

## Status: 🔴 NOT STARTED
## One task only. Do NOT read other project files except those listed below.

## What you're doing

The 15 scenes of the EduVidQA "Kitchen Tour" explainer have all been rendered and stitched into `media/videos/explainer_v4/EduVidQAExplainer_v4_480p.mp4` (3:32, 480p15). Individual scenes were QC'd by their builder sessions (A–E) but the full cut has **never been reviewed as a single piece**. The Director has flagged it as broken in unspecified ways.

Your job:
1. Watch / inspect the full cut by extracting keyframes at scene boundaries.
2. Identify defects: black frames, missing characters, broken text, wrong colors, continuity breaks (especially the OrderTicket prop in Acts II→III), pacing issues.
3. Fix each defect by editing the relevant `scripts/explainer_v4/scene_NN_*.py` file and re-rendering ONLY that scene.
4. Re-stitch the full cut.
5. Re-QC at boundaries to confirm fixes.

## Pre-flight

1. Activate venv: `source /Users/shubhamkumar/eduvidqa-product/.venv/bin/activate`
2. Verify the existing artifacts:
   ```bash
   ls -lh media/videos/explainer_v4/EduVidQAExplainer_v4_480p.mp4
   ls media/videos/scene_*/480p15/*.mp4 | wc -l   # expect 15
   ```
3. Read these files only:
   - `scripts/explainer_v4_lib/__init__.py` (to understand what helpers exist)
   - `interfaces/explainer_v4/README_MANAGER.md` (conventions: dark bg, gold `#FFD66B`, ticket prop, etc.)
   - The HANDOFF Kitchen Tour script lives in `HANDOFF.md` under "EduVidQA — *Kitchen Tour*" — read ONLY that section, not the rest of the file.

## Scene → file map (for fixes)

| # | mp4 | source file | class |
|---|---|---|---|
| 1 | scene_01_cold_open | `scripts/explainer_v4/scene_01_cold_open.py` | `Scene01ColdOpen` |
| 2 | scene_02_quill_chunks | `scripts/explainer_v4/scene_02_quill_chunks.py` | `Scene02QuillChunks` |
| 3 | scene_03_lens_keyframes | `scripts/explainer_v4/scene_03_lens_keyframes.py` | `Scene03LensKeyframes` |
| 4 | scene_04_indie_files | `scripts/explainer_v4/scene_04_indie_files.py` | `Scene04IndieFiles` |
| 5 | scene_05_lights_up | `scripts/explainer_v4/scene_05_lights_up.py` | `Scene05LightsUp` |
| 6 | scene_06_customer_pauses | `scripts/explainer_v4/scene_06_customer_pauses.py` | `Scene06CustomerPauses` |
| 7 | scene_07_maitre_routes | `scripts/explainer_v4/scene_07_maitre_routes.py` | `Scene07MaitreRoutes` |
| 8 | scene_08_indie_retrieves | `scripts/explainer_v4/scene_08_indie_retrieves.py` | `Scene08IndieRetrieves` |
| 9 | scene_09_timestamp_rerank | `scripts/explainer_v4/scene_09_timestamp_rerank.py` | `Scene09TimestampRerank` |
| 10 | scene_10_live_frame | `scripts/explainer_v4/scene_10_live_frame.py` | `Scene10LiveFrame` |
| 11 | scene_11_chef_cooks | `scripts/explainer_v4/scene_11_chef_cooks.py` | `Scene11ChefCooks` |
| 12 | scene_12_critic_tastes | `scripts/explainer_v4/scene_12_critic_tastes.py` | `Scene12CriticTastes` |
| 13 | scene_13_delivery | `scripts/explainer_v4/scene_13_delivery.py` | `Scene13Delivery` |
| 14 | scene_14_two_doors | `scripts/explainer_v4/scene_14_two_doors.py` | `Scene14TwoDoors` |
| 15 | scene_15_curtain_call | `scripts/explainer_v4/scene_15_curtain_call.py` | `Scene15CurtainCall` |

## Phase 1 — Boundary QC (image budget: 7 frames)

Goal: catch defects at each act-boundary. 7 frames covers all 4 act transitions + 3 sanity checks.

Extract these specific frames from the **stitched** cut (cumulative timestamps based on per-scene durations: 7.5, 9.3, 12.7, 17.7, 7.1, 13.0, 9.9, 21.5, 12.0, 13.0, 23.3, 10.7, 16.7, 23.9, 14.3 → boundaries at ~0:30, 0:55, 2:30, 3:00):

```bash
cd /Users/shubhamkumar/eduvidqa-product
QC=media/qc_director/full_cut && mkdir -p "$QC"
IN=media/videos/explainer_v4/EduVidQAExplainer_v4_480p.mp4

# 7 strategic frames: act boundaries + climax mid + tagline + final
ffmpeg -y -ss 30  -i "$IN" -vframes 1 -q:v 2 "$QC/01_act1_end.jpg"     2>/dev/null
ffmpeg -y -ss 55  -i "$IN" -vframes 1 -q:v 2 "$QC/02_act2_start.jpg"   2>/dev/null
ffmpeg -y -ss 130 -i "$IN" -vframes 1 -q:v 2 "$QC/03_chef_climax.jpg"  2>/dev/null
ffmpeg -y -ss 150 -i "$IN" -vframes 1 -q:v 2 "$QC/04_critic_stamps.jpg" 2>/dev/null
ffmpeg -y -ss 175 -i "$IN" -vframes 1 -q:v 2 "$QC/05_act2_end.jpg"     2>/dev/null
ffmpeg -y -ss 200 -i "$IN" -vframes 1 -q:v 2 "$QC/06_tagline.jpg"      2>/dev/null
ffmpeg -y -ss 210 -i "$IN" -vframes 1 -q:v 2 "$QC/07_final.jpg"        2>/dev/null
ls -lh "$QC/"
```

`view_image` all 7. For each, write in your Worker Log:
- What scene this frame is from (best guess based on the script)
- Whether it looks correct vs. the script's intent
- Specific defects: `[BLACK]`, `[MISSING_CHAR:<name>]`, `[WRONG_COLOR:<expected>/<actual>]`, `[BROKEN_TEXT:<what>]`, `[CONTINUITY:<what>]`, `[OK]`

## Phase 2 — Per-scene deep QC (only for scenes flagged in Phase 1)

For each scene with a defect, extract 2 more frames from THAT scene's individual mp4 (start + 75% mark) to localize the defect:

```bash
SCENE=scene_NN_<name>; CLASS=SceneNN<Name>
IN=media/videos/$SCENE/480p15/$CLASS.mp4
QC=media/qc_director/$SCENE && mkdir -p "$QC"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
ffmpeg -y -ss 0.5 -i "$IN" -vframes 1 -q:v 2 "$QC/start.jpg" 2>/dev/null
ffmpeg -y -ss $(echo "$DUR*0.75" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/q3.jpg" 2>/dev/null
```

**Image budget for Phase 2: max 2 frames per defective scene, max 3 defective scenes deep-dived (= 6 frames max). Total session budget: 7 + 6 = 13 frames. If more than 3 scenes need deep dives, fix the worst 3 first, re-stitch, and let the manager dispatch a follow-up session.**

## Phase 3 — Fix

For each identified defect:
1. Read the relevant `scene_NN_*.py` file (one read, ≤ 200 lines each — they should be small).
2. Make the minimal fix. Examples of common defects to look for:
   - Speech bubble exceeds 5 words → `ValueError` from lib raises during render → check stderr.
   - Character placed off-screen (camera frame is roughly x ∈ [-7, 7], y ∈ [-4, 4]).
   - Color hex typo (gold should be `#FFD66B` everywhere; bg `#0e1117`).
   - Text overflowing the plate / ticket / sign.
   - OrderTicket position mismatch between scene N's end and scene N+1's start (constants at top of each scene file in C).
   - `Transform` source/target shapes incompatible — common cause of garbled mid-animation frames.
3. Re-render that one scene:
   ```bash
   manim -ql scripts/explainer_v4/scene_NN_<name>.py SceneNN<Name>
   ```
4. Re-extract the deep-dive frames for that scene to confirm fix.
5. Move to next defect.

## Phase 4 — Re-stitch and re-QC the boundaries

```bash
cd /Users/shubhamkumar/eduvidqa-product
: > /tmp/concat_v4.txt
for i in 01_cold_open:Scene01ColdOpen 02_quill_chunks:Scene02QuillChunks \
         03_lens_keyframes:Scene03LensKeyframes 04_indie_files:Scene04IndieFiles \
         05_lights_up:Scene05LightsUp 06_customer_pauses:Scene06CustomerPauses \
         07_maitre_routes:Scene07MaitreRoutes 08_indie_retrieves:Scene08IndieRetrieves \
         09_timestamp_rerank:Scene09TimestampRerank 10_live_frame:Scene10LiveFrame \
         11_chef_cooks:Scene11ChefCooks 12_critic_tastes:Scene12CriticTastes \
         13_delivery:Scene13Delivery 14_two_doors:Scene14TwoDoors \
         15_curtain_call:Scene15CurtainCall; do
  echo "file '$PWD/media/videos/scene_${i%%:*}/480p15/${i##*:}.mp4'" >> /tmp/concat_v4.txt
done
ffmpeg -y -f concat -safe 0 -i /tmp/concat_v4.txt -c copy \
  media/videos/explainer_v4/EduVidQAExplainer_v4_480p.mp4 2>&1 | tail -3
ffprobe -v error -show_entries format=duration -of csv=p=0 \
  media/videos/explainer_v4/EduVidQAExplainer_v4_480p.mp4
```

Note: cumulative timestamps in Phase 1 will shift if any scene's duration changed by more than ~0.5 s. Recompute boundaries from the new per-scene `ffprobe` durations before extracting Phase-4 verification frames.

## Constraints

- **Image budget: 13 frames max** (7 boundary + 6 deep-dive). Do NOT exceed. If you run out, write up findings + fixes-needed in Worker Log and let manager dispatch Session G.
- Native resolution (854×480), `-q:v 2`. ~120 KB per frame.
- Do NOT modify `scripts/explainer_v4_lib/`. If a lib bug is the root cause, document it in Worker Log and work around it inside the scene file (e.g. duplicate the helper locally with the fix).
- Do NOT add `xfade` transitions, do NOT re-render at `-qm`, do NOT add audio. Those are separate sessions.
- Do NOT touch `app_gradio.py`, `pipeline/`, `backend/`, `frontend/` — only `scripts/explainer_v4/scene_*.py`.

## Worker Log
_Write progress here. Final entry = audit report._

Recommended structure:
```
### Phase 1 findings (per boundary frame)
- 01_act1_end.jpg: [scene 4 end] OK / DEFECT: ...
- ...

### Phase 2 deep-dive frames
- scene_NN: ...

### Phase 3 fixes applied
- scene_NN: changed X to Y because Z
- ...

### Phase 4 re-stitch
- new total duration: ___ s
- boundary re-QC: ___
```

## Before Marking Complete — Self-Audit
- [ ] Phase 1: 7 boundary frames extracted and viewed; per-frame verdict in log
- [ ] Phase 2: deep-dive frames extracted ONLY for defective scenes (≤ 6 frames total)
- [ ] Phase 3: every defect identified in Phase 1/2 has either (a) been fixed and the scene re-rendered, or (b) been explicitly flagged as out-of-scope in the log with reason
- [ ] Phase 4: full cut re-stitched; new duration noted; if boundaries shifted >0.5 s, boundary frames re-extracted to confirm no regressions
- [ ] Total image budget ≤ 13 frames (count exact number in audit)
- [ ] No edits outside `scripts/explainer_v4/scene_*.py`
- [ ] Audit Report in Worker Log: list of defects found, list of fixes applied, list of scenes re-rendered, new full-cut duration, frame count used
