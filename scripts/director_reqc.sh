#!/usr/bin/env bash
# Director Re-QC — re-extract every rendered scene at native resolution + max JPEG quality.
# Output: media/qc_director/<scene>/{start,mid,end}.jpg  (~120 KB each)
# Then view_image each.

set -e
cd "$(dirname "$0")/.."

SCENES=(
  "scene_01_cold_open:Scene01ColdOpen"
  "scene_02_quill_chunks:Scene02QuillChunks"
  "scene_03_lens_keyframes:Scene03LensKeyframes"
  "scene_04_indie_files:Scene04IndieFiles"
  "scene_05_lights_up:Scene05LightsUp"
  "scene_06_customer_pauses:Scene06CustomerPauses"
  "scene_07_maitre_routes:Scene07MaitreRoutes"
  "scene_08_indie_retrieves:Scene08IndieRetrieves"
  "scene_09_timestamp_rerank:Scene09TimestampRerank"
  "scene_10_live_frame:Scene10LiveFrame"
  "scene_11_chef_cooks:Scene11ChefCooks"
  "scene_12_critic_tastes:Scene12CriticTastes"
  "scene_13_delivery:Scene13Delivery"
  "scene_14_two_doors:Scene14TwoDoors"
  "scene_15_curtain_call:Scene15CurtainCall"
)

for entry in "${SCENES[@]}"; do
  SCENE="${entry%%:*}"
  CLASS="${entry##*:}"
  IN="media/videos/$SCENE/480p15/$CLASS.mp4"
  OUT="media/qc_director/$SCENE"

  if [[ ! -f "$IN" ]]; then
    echo "[skip] $SCENE — no mp4 yet"
    continue
  fi

  mkdir -p "$OUT"
  DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
  MID=$(echo "$DUR/2" | bc -l)
  END=$(echo "$DUR-0.3" | bc -l)

  # Native resolution (no -vf scale), max quality (-q:v 2 ≈ near-lossless JPEG)
  ffmpeg -y -ss 0.5  -i "$IN" -vframes 1 -q:v 2 "$OUT/start.jpg" 2>/dev/null
  ffmpeg -y -ss "$MID" -i "$IN" -vframes 1 -q:v 2 "$OUT/mid.jpg"   2>/dev/null
  ffmpeg -y -ss "$END" -i "$IN" -vframes 1 -q:v 2 "$OUT/end.jpg"   2>/dev/null

  printf "[ok]   %-32s  dur=%5.1fs  frames -> %s/{start,mid,end}.jpg\n" \
    "$SCENE" "$DUR" "$OUT"
done

echo
echo "Total frames written:"
find media/qc_director -name "*.jpg" | wc -l
echo
echo "Per-frame sizes (sample):"
ls -lh media/qc_director/*/start.jpg 2>/dev/null | head -5
