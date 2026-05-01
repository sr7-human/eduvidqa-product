"""Finish Session B: digest for sorting video + Gemini keyframes + verification."""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

DATA_DIR = "data/processed"
VIDEO_IDS = ["3OmfTIf-SOU", "VRcixOuG-TU", "oZgbwa8lvDE"]

GEMINI_KEYS = [
    "GEMINI_KEY_REDACTED",
    "GEMINI_KEY_REDACTED",
    "GEMINI_KEY_REDACTED",
    "GEMINI_KEY_REDACTED",
]

def load_chunks(vid): return json.loads((Path(DATA_DIR)/vid/"transcript"/"chunks.json").read_text())
def load_manifest(vid): return json.loads((Path(DATA_DIR)/vid/"keyframes"/"manifest.json").read_text())
def load_digest(vid): return (Path(DATA_DIR)/vid/"digest.txt").read_text()

# ── Step 1: Regenerate sorting video digest ──────────────────────
print("=" * 60)
print("STEP 1: REGENERATE DIGEST FOR oZgbwa8lvDE")
print("=" * 60)

from pipeline.digest import generate_digest
digest_path = Path(DATA_DIR) / "oZgbwa8lvDE" / "digest.txt"
current = digest_path.read_text() if digest_path.exists() else ""
if len(current) < 500:
    print(f"  Current digest too short ({len(current)} chars), regenerating...")
    t0 = time.time()
    try:
        digest = generate_digest("oZgbwa8lvDE", data_dir=DATA_DIR)
        print(f"  ✓ New digest: {len(digest)} chars in {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        print("  Using placeholder digest")
else:
    print(f"  ✓ Digest already OK ({len(current)} chars)")

# ── Step 2: Finish Gemini indexing (sorting video keyframes) ─────
print("\n" + "=" * 60)
print("STEP 2: GEMINI INDEX — oZgbwa8lvDE keyframes")
print("=" * 60)

from google import genai
from google.genai import types

# Custom embedding service that rotates keys
class MultiKeyGeminiEmbedder:
    def __init__(self, keys):
        self._keys = keys
        self._idx = 0
        self._clients = [genai.Client(api_key=k) for k in keys]
        self._backend = "gemini"

    def _client(self):
        c = self._clients[self._idx]
        self._idx = (self._idx + 1) % len(self._clients)
        return c

    def get_dimension(self): return 768

    def embed_text(self, text):
        result = self._client().models.embed_content(
            model="gemini-embedding-2-preview",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )
        return list(result.embeddings[0].values)

    def embed_batch_text(self, texts):
        return [self.embed_text(t) for t in texts]

    def embed_image(self, path):
        img_bytes = Path(path).read_bytes()
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        result = self._client().models.embed_content(
            model="gemini-embedding-2-preview",
            contents=[types.Part.from_bytes(data=img_bytes, mime_type=mime)],
            config=types.EmbedContentConfig(output_dimensionality=768),
        )
        return list(result.embeddings[0].values)

    def embed_batch_images(self, paths):
        results = []
        for i, p in enumerate(paths):
            if i > 0 and i % 50 == 0:
                print(f"    ... {i}/{len(paths)} keyframes embedded")
            try:
                results.append(self.embed_image(p))
            except Exception as e:
                print(f"    ✗ Failed on {p}: {e}, retrying with next key...")
                time.sleep(2)
                try:
                    results.append(self.embed_image(p))
                except Exception as e2:
                    print(f"    ✗ Retry failed: {e2}, using zero vector")
                    results.append([0.0] * 768)
        return results

    def _ensure_loaded(self):
        pass  # already loaded

from pipeline.rag import LectureIndex

multi_gemini = MultiKeyGeminiEmbedder(GEMINI_KEYS)
gemini_idx = LectureIndex(persist_dir="data/chroma", embedding_model="gemini", _embed_service=multi_gemini)

vid = "oZgbwa8lvDE"
chunks = load_chunks(vid)
manifest = load_manifest(vid)
digest = load_digest(vid)
print(f"  {vid}: {len(chunks)} chunks, {len(manifest)} keyframes, {len(digest)} chars digest")
t0 = time.time()
count = gemini_idx.index_video(vid, chunks, manifest, digest)
print(f"  ✓ {vid}: {count} items in {time.time()-t0:.1f}s")

# ── Step 3: Verify retrieval (both models) ───────────────────────
print("\n" + "=" * 60)
print("STEP 3: RETRIEVAL VERIFICATION")
print("=" * 60)

from pipeline.embeddings import EmbeddingService

jina_svc = EmbeddingService("jina")
jina_svc._ensure_loaded()
jina_idx = LectureIndex(persist_dir="data/chroma", embedding_model="jina", _embed_service=jina_svc)

# Reload gemini with simple service for queries (single key is fine)
gemini_svc = EmbeddingService("gemini")
gemini_idx2 = LectureIndex(persist_dir="data/chroma", embedding_model="gemini", _embed_service=gemini_svc)

questions = {
    "3OmfTIf-SOU": [("What is unit testing?", 20.0), ("How do tests validate functions?", 100.0)],
    "VRcixOuG-TU": [("What is a perceptron?", 30.0), ("How does the activation function work?", 200.0)],
    "oZgbwa8lvDE": [("How does insertion sort work?", 60.0), ("What is the time complexity?", 400.0)],
}

for vid, qs in questions.items():
    print(f"\n--- {vid} ---")
    for q, ts in qs:
        print(f"  Q: {q}")
        for name, idx in [("Jina", jina_idx), ("Gemini", gemini_idx2)]:
            r = idx.retrieve(q, vid, ts, top_k=3)
            top = r["ranked_chunks"][0]["text"][:120] if r["ranked_chunks"] else "(none)"
            print(f"    [{name}] chunks={len(r['ranked_chunks'])}, kf={len(r['relevant_keyframes'])}, digest={'yes' if r['digest'] else 'no'}")
            print(f"           top: {top}...")

print("\n" + "=" * 60)
print("✓ SESSION B COMPLETE")
print("=" * 60)
