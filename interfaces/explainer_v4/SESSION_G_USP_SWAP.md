# Session G — USP Question Swap

## Status: 🔴 NOT STARTED
## One task only. Do NOT read other project files except those listed below.

## What you're doing

The current `OrderTicket` question across the explainer is **"Why does the gradient point uphill?"** — a generic textbook question that ChatGPT can answer perfectly without ever seeing the lecture. This undermines the USP scene (Scene 14) where we contrast against generic chatbots: the audience won't believe the "Generic Diner shrug" because they know ChatGPT *would* answer it.

Replace the question across **4 scene files** with one that ChatGPT literally cannot answer without the video:

> **New question: `What does the blue arrow at 4:32 mean?`**

It's a pointer-to-screen question requiring the live frame + a specific keyframe — exactly what our multimodal pipeline is built for. Generic chatbots can only respond *"…blue arrow? what arrow?"* — which is now a credible failure, not a strawman.

## Pre-flight

1. Activate venv: `source /Users/shubhamkumar/eduvidqa-product/.venv/bin/activate`
2. Verify the 4 target files exist:
   ```bash
   ls scripts/explainer_v4/scene_06_customer_pauses.py \
      scripts/explainer_v4/scene_08_indie_retrieves.py \
      scripts/explainer_v4/scene_11_chef_cooks.py \
      scripts/explainer_v4/scene_14_two_doors.py
   ```
3. Read those 4 files end-to-end before editing (they're each < 250 lines per the v4 conventions).
4. Read `scripts/explainer_v4_lib/order_ticket.py` to understand the `OrderTicket` API (you'll be passing the new question string into its constructor).

## Required changes per file

### 1. `scene_06_customer_pauses.py` — `Scene06CustomerPauses`
- The customer's notepad text: change to `"What does the blue arrow at 4:32 mean?"`
- The `OrderTicket(...)` instantiation: change `question=` to `"What does the blue arrow at 4:32 mean?"` (keep `timestamp="04:32"`, `video_id="3OmfTIf-SOU"` unchanged).
- The on-screen ticket text in any commented script docstring at top of file: also update so future readers aren't confused.

### 2. `scene_08_indie_retrieves.py` — `Scene08IndieRetrieves`
- Recreates the OrderTicket locally for independence. Update the `question=` arg here too.
- The "question text lifts off as glowing letters" animation — the Text mobject for the lifted question must use the new string.

### 3. `scene_11_chef_cooks.py` — `Scene11ChefCooks`
- The progressive plating phrases must change. Replace the existing 4 phrases with these 4 (preserve `AddTextLetterByLetter` per phrase + gold tag drops):
  1. *"The blue arrow at 4:32 shows the negative gradient direction —"*
  2. *"the step we'd take to reduce loss [04:32]"* + drop gold tag `[04:32]` on rim
  3. *"Compare it to the red arrow she drew at 2:15"* + drop gold tag `[02:15]` on rim
  4. *"— same idea, opposite sign on the loss surface [05:02]"* + drop gold tag `[05:02]` on rim
- Note the gold-tag timestamps changed from `[04:30]/[04:35]/[05:02]` to `[04:32]/[02:15]/[05:02]`. The 02:15 tag is intentional — it demonstrates cross-reference retrieval (a different moment in the same lecture), reinforcing the "we cook from YOUR lecture" message.
- All gold tags still use color `#FFD66B`.

### 4. `scene_14_two_doors.py` — `Scene14TwoDoors`
- The customer's question bubble at the **left door** (Generic Diner): change from `"...but where in MY lecture?"` to `"What does the blue arrow at 4:32 mean?"` (keep the original ≤5-word rule by splitting if needed — `SpeechBubble` will raise if too long, so use 2 bubbles in sequence: first `"Blue arrow at 4:32?"`, then chef shrugs and bubbles `"...what arrow?"`).
- The right-door (EduVidQA Kitchen) plate must show the same question being answered with gold `[mm:ss]` tags pointing to lecture frames. Use the same 3 timestamps as Scene 11: `[04:32]`, `[02:15]`, `[05:02]`.
- Tagline at end is **unchanged**: `"Every answer is traceable to a moment in the lecture."`

## Steps

1. Make the 4 file edits above. Keep edits minimal — only the strings/phrases listed.
2. Re-render the 4 affected scenes:
   ```bash
   cd /Users/shubhamkumar/eduvidqa-product
   manim -ql scripts/explainer_v4/scene_06_customer_pauses.py Scene06CustomerPauses
   manim -ql scripts/explainer_v4/scene_08_indie_retrieves.py Scene08IndieRetrieves
   manim -ql scripts/explainer_v4/scene_11_chef_cooks.py Scene11ChefCooks
   manim -ql scripts/explainer_v4/scene_14_two_doors.py Scene14TwoDoors
   ```
3. **Visual QC** — extract 6 native-resolution `-q:v 2` frames (1 mid-frame each for scenes 6 & 8 to confirm question swap, 2 frames for scene 11 to confirm new plating, 2 frames for scene 14 to confirm new bubble + plate):
   ```bash
   for s in 06_customer_pauses:Scene06CustomerPauses 08_indie_retrieves:Scene08IndieRetrieves; do
     SCENE="scene_${s%%:*}"; CLASS="${s##*:}"
     QC="media/qc_director/$SCENE" && mkdir -p "$QC"
     IN="media/videos/$SCENE/480p15/$CLASS.mp4"
     DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
     ffmpeg -y -ss $(echo "$DUR-0.3" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/end.jpg" 2>/dev/null
   done

   QC=media/qc_director/scene_11_chef_cooks && mkdir -p "$QC"
   IN=media/videos/scene_11_chef_cooks/480p15/Scene11ChefCooks.mp4
   DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
   ffmpeg -y -ss $(echo "$DUR/2" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/mid.jpg" 2>/dev/null
   ffmpeg -y -ss $(echo "$DUR-0.3" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/end.jpg" 2>/dev/null

   QC=media/qc_director/scene_14_two_doors && mkdir -p "$QC"
   IN=media/videos/scene_14_two_doors/480p15/Scene14TwoDoors.mp4
   DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
   ffmpeg -y -ss $(echo "$DUR*0.3" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/left.jpg" 2>/dev/null
   ffmpeg -y -ss $(echo "$DUR*0.7" | bc -l) -i "$IN" -vframes 1 -q:v 2 "$QC/right.jpg" 2>/dev/null
   ```
   `view_image` on all 6. Confirm:
   - Scene 6 end: ticket reads `"What does the blue arrow at 4:32 mean?"` legibly.
   - Scene 8 end: same question visible on/around the ticket and/or the glowing-arrow text.
   - Scene 11 mid: plate has at least 2 of the new phrases written; one gold tag visible.
   - Scene 11 end: all 4 phrases on plate, 3 gold tags `[04:32]/[02:15]/[05:02]` in `#FFD66B`.
   - Scene 14 left frame: generic chef shrug + new bubbles about "blue arrow".
   - Scene 14 right frame: plate with 3 gold `[mm:ss]` tags matching Scene 11.

4. Re-stitch the full cut (paste verbatim — same script as before):
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

## Constraints

- **Image budget: 6 frames max.** Do not exceed.
- Do NOT modify `scripts/explainer_v4_lib/`. The `OrderTicket` constructor accepts arbitrary question strings — no lib change needed.
- Do NOT touch any scene file other than 6, 8, 11, 14.
- Do NOT change durations significantly. Each affected scene should still land within ± 1 s of its previous duration:
  - Scene 6: was 13.00 s
  - Scene 8: was 21.47 s
  - Scene 11: was 23.33 s
  - Scene 14: was 23.93 s
  If a scene drifts more than ± 1 s, tighten/lengthen `self.wait()` calls to compensate — do not let the new text inflate runtime.
- Speech-bubble rule still applies: ≤ 5 words per bubble. The Scene-14 left-door customer line MUST be split into two sequential bubbles (`"Blue arrow at 4:32?"` then chef's `"...what arrow?"`) to stay under the limit.
- Tagline string (Scene 14 end) is **NOT** changing: still `"Every answer is traceable to a moment in the lecture."`

## Worker Log
_Write progress here. Final entry = audit report._

## Before Marking Complete — Self-Audit
- [ ] All 4 files edited (paste a one-line diff summary per file in audit)
- [ ] All 4 scenes re-rendered, exit code 0
- [ ] All 4 scene durations within ± 1 s of their pre-swap values (paste ffprobe outputs for old vs new)
- [ ] 6 QC frames extracted at native res + `-q:v 2` and viewed; per-frame confirmation of new text/tags
- [ ] Full cut re-stitched; new total duration noted (paste ffprobe output)
- [ ] Tagline `"Every answer is traceable to a moment in the lecture."` still present unchanged in Scene 14
- [ ] Gold color `#FFD66B` preserved on all citation tags
- [ ] No edits outside the 4 assigned files
- [ ] Audit Report in Worker Log: per-file diff summary, render exit codes, old/new durations, QC frame descriptions, new full-cut duration
