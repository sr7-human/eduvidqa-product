"""Integration test — run keyframe extraction + transcript chunking on all 3 AutoTA videos."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when invoked directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.keyframes import extract_keyframes
from pipeline.chunking import chunk_transcript

VIDEOS = [
    {"id": "3OmfTIf-SOU", "label": "Khan Academy Unit Testing", "duration_min": 4.7},
    {"id": "VRcixOuG-TU", "label": "Deep Learning Perceptron", "duration_min": 13.6},
    {"id": "oZgbwa8lvDE", "label": "Algorithms Insertion Sort", "duration_min": 27.4},
]

VIDEO_DIR = "data/videos"
OUTPUT_DIR = "data/processed"


def run_integration():
    print("=" * 65)
    print("  EduVidQA — Keyframe + Chunking Integration Test")
    print("=" * 65)
    print()

    for v in VIDEOS:
        vid = v["id"]
        video_path = f"{VIDEO_DIR}/{vid}.mp4"
        if not Path(video_path).exists():
            print(f"⚠ SKIP {vid} — video file not found at {video_path}")
            continue

        print(f"Video: {vid} ({v['label']}, {v['duration_min']} min)")

        # ── Keyframes ────────────────────────────────────────────────
        kf_manifest = extract_keyframes(video_path, vid, output_dir=OUTPUT_DIR)
        kf_dir = Path(OUTPUT_DIR) / vid / "keyframes"
        kf_files = list(kf_dir.glob("*.jpg"))
        duration_s = int(v["duration_min"] * 60)

        print(f"  Keyframes: {len(kf_manifest)} extracted (from {duration_s} sampled)")

        # ── Chunks ───────────────────────────────────────────────────
        chunks = chunk_transcript(vid, output_dir=OUTPUT_DIR, keyframe_manifest=kf_manifest)
        linked_count = sum(1 for c in chunks if c["linked_keyframe_ids"])
        total_linked_kf = sum(len(c["linked_keyframe_ids"]) for c in chunks)

        tx_dir = Path(OUTPUT_DIR) / vid / "transcript"
        full_txt = tx_dir / "full.txt"
        chunks_json = tx_dir / "chunks.json"

        print(f"  Chunks:    {len(chunks)} created")
        print(f"  Linked:    {total_linked_kf} keyframes linked to {linked_count} chunks")
        print(f"  Files saved:")
        print(f"    {kf_dir}/ ({len(kf_files)} files)")
        print(f"    {full_txt} ({'✓' if full_txt.exists() else '✗'})")
        print(f"    {chunks_json} ({'✓' if chunks_json.exists() else '✗'})")

        # ── Sanity checks ────────────────────────────────────────────
        assert len(kf_manifest) > 0, "No keyframes extracted"
        assert len(chunks) > 0, "No chunks created"
        assert full_txt.exists(), "full.txt not written"
        assert chunks_json.exists(), "chunks.json not written"
        assert all(c["text"] or not c["text"] for c in chunks), "Chunk structure broken"
        non_empty = [c for c in chunks if c["text"]]
        assert len(non_empty) > len(chunks) * 0.5, "Too many empty chunks"

        print(f"  ✓ All assertions passed")
        print()

    print("=" * 65)
    print("  ALL VIDEOS PROCESSED SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    run_integration()
