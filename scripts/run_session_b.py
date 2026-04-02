"""Run the full Session B pipeline: digest + index (Jina + Gemini) for all 3 videos."""

import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

DATA_DIR = "data/processed"
VIDEO_IDS = ["3OmfTIf-SOU", "VRcixOuG-TU", "oZgbwa8lvDE"]


def load_chunks(video_id: str) -> list[dict]:
    p = Path(DATA_DIR) / video_id / "transcript" / "chunks.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_manifest(video_id: str) -> list[dict]:
    p = Path(DATA_DIR) / video_id / "keyframes" / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def run():
    # ── Step 1: Generate digests ─────────────────────────────────
    print("=" * 60)
    print("STEP 1: DIGEST GENERATION (Groq Llama 4 Scout)")
    print("=" * 60)

    from pipeline.digest import generate_digest

    for vid in VIDEO_IDS:
        digest_path = Path(DATA_DIR) / vid / "digest.txt"
        if digest_path.exists() and digest_path.stat().st_size > 200:
            print(f"  ✓ {vid}: digest already exists ({digest_path.stat().st_size} chars), skipping")
            continue
        print(f"  → Generating digest for {vid} ...")
        t0 = time.time()
        try:
            digest = generate_digest(vid, data_dir=DATA_DIR)
            print(f"  ✓ {vid}: {len(digest)} chars in {time.time()-t0:.1f}s")
        except Exception as e:
            print(f"  ✗ {vid}: FAILED — {e}")
            # Write a placeholder so indexing can proceed
            digest_path.write_text(f"[Digest generation failed: {e}]", encoding="utf-8")

    # ── Step 2: Index with Jina CLIP v2 (local) ──────────────────
    print()
    print("=" * 60)
    print("STEP 2: JINA CLIP v2 INDEXING (local, 1024-dim)")
    print("=" * 60)

    from pipeline.embeddings_v2 import EmbeddingService
    from pipeline.rag_v2 import LectureIndex

    jina_svc = EmbeddingService("jina")
    jina_svc._ensure_loaded()
    jina_index = LectureIndex(
        persist_dir="data/chroma",
        embedding_model="jina",
        _embed_service=jina_svc,
    )

    for vid in VIDEO_IDS:
        print(f"\n  → Indexing {vid} (Jina) ...")
        chunks = load_chunks(vid)
        manifest = load_manifest(vid)
        digest = (Path(DATA_DIR) / vid / "digest.txt").read_text(encoding="utf-8")

        print(f"    Chunks: {len(chunks)}, Keyframes: {len(manifest)}, Digest: {len(digest)} chars")
        t0 = time.time()
        count = jina_index.index_video(vid, chunks, manifest, digest)
        elapsed = time.time() - t0
        print(f"  ✓ {vid}: {count} items indexed in {elapsed:.1f}s")

    # Verify retrieval
    print("\n  --- Jina retrieval smoke test ---")
    for vid in VIDEO_IDS:
        result = jina_index.retrieve("What is this lecture about?", vid, 30.0, top_k=3)
        n_chunks = len(result["ranked_chunks"])
        n_kf = len(result["relevant_keyframes"])
        has_digest = len(result["digest"]) > 0
        print(f"  {vid}: {n_chunks} chunks, {n_kf} keyframes, digest={'yes' if has_digest else 'no'}")

    # ── Step 3: Index with Gemini Embedding 2 (API) ──────────────
    print()
    print("=" * 60)
    print("STEP 3: GEMINI EMBEDDING 2 INDEXING (API, 768-dim)")
    print("=" * 60)

    gemini_svc = EmbeddingService("gemini")
    gemini_index = LectureIndex(
        persist_dir="data/chroma",
        embedding_model="gemini",
        _embed_service=gemini_svc,
    )

    for vid in VIDEO_IDS:
        print(f"\n  → Indexing {vid} (Gemini) ...")
        chunks = load_chunks(vid)
        manifest = load_manifest(vid)
        digest = (Path(DATA_DIR) / vid / "digest.txt").read_text(encoding="utf-8")

        # For Gemini, skip keyframe images (API cost/quota) — text only
        print(f"    Chunks: {len(chunks)}, Keyframes: {len(manifest)}, Digest: {len(digest)} chars")
        t0 = time.time()
        count = gemini_index.index_video(vid, chunks, manifest, digest)
        elapsed = time.time() - t0
        print(f"  ✓ {vid}: {count} items indexed in {elapsed:.1f}s")

    # Verify retrieval
    print("\n  --- Gemini retrieval smoke test ---")
    for vid in VIDEO_IDS:
        result = gemini_index.retrieve("What is this lecture about?", vid, 30.0, top_k=3)
        n_chunks = len(result["ranked_chunks"])
        n_kf = len(result["relevant_keyframes"])
        has_digest = len(result["digest"]) > 0
        print(f"  {vid}: {n_chunks} chunks, {n_kf} keyframes, digest={'yes' if has_digest else 'no'}")

    print()
    print("=" * 60)
    print("ALL DONE")
    print("=" * 60)


if __name__ == "__main__":
    run()
