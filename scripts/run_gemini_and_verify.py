"""Run Gemini indexing + verify retrieval for all 3 videos."""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

DATA_DIR = "data/processed"
VIDEO_IDS = ["3OmfTIf-SOU", "VRcixOuG-TU", "oZgbwa8lvDE"]

def load_chunks(vid): return json.loads((Path(DATA_DIR)/vid/"transcript"/"chunks.json").read_text())
def load_manifest(vid): return json.loads((Path(DATA_DIR)/vid/"keyframes"/"manifest.json").read_text())
def load_digest(vid): return (Path(DATA_DIR)/vid/"digest.txt").read_text()

from pipeline.embeddings import EmbeddingService
from pipeline.rag import LectureIndex

# ── Gemini indexing ──────────────────────────────────────────────
print("=" * 60)
print("GEMINI EMBEDDING 2 INDEXING (API, 768-dim)")
print("=" * 60)

gemini_svc = EmbeddingService("gemini")
gemini_idx = LectureIndex(persist_dir="data/chroma", embedding_model="gemini", _embed_service=gemini_svc)

for vid in VIDEO_IDS:
    chunks = load_chunks(vid)
    manifest = load_manifest(vid)
    digest = load_digest(vid)
    print(f"\n→ {vid}: {len(chunks)} chunks, {len(manifest)} keyframes, {len(digest)} chars digest")
    t0 = time.time()
    count = gemini_idx.index_video(vid, chunks, manifest, digest)
    print(f"✓ {vid}: {count} items in {time.time()-t0:.1f}s")

# ── Verify retrieval (both models) ──────────────────────────────
print("\n" + "=" * 60)
print("RETRIEVAL VERIFICATION")
print("=" * 60)

# Reload Jina index
jina_svc = EmbeddingService("jina")
jina_svc._ensure_loaded()
jina_idx = LectureIndex(persist_dir="data/chroma", embedding_model="jina", _embed_service=jina_svc)

questions = {
    "3OmfTIf-SOU": ("What is unit testing?", 20.0),
    "VRcixOuG-TU": ("What is a perceptron?", 30.0),
    "oZgbwa8lvDE": ("How does insertion sort work?", 60.0),
}

for vid, (q, ts) in questions.items():
    print(f"\n--- {vid} ---")
    print(f"Q: {q}")
    for name, idx in [("Jina", jina_idx), ("Gemini", gemini_idx)]:
        r = idx.retrieve(q, vid, ts, top_k=3)
        top = r["ranked_chunks"][0]["text"][:100] if r["ranked_chunks"] else "(none)"
        print(f"  [{name}] chunks={len(r['ranked_chunks'])}, kf={len(r['relevant_keyframes'])}, digest={'yes' if r['digest'] else 'no'}")
        print(f"         top: {top}…")

print("\n✓ ALL DONE")
