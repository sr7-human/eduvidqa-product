"""Index videos with Gemini Embedding 2 into ChromaDB."""
import json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

from pipeline.embeddings_v2 import EmbeddingService
from pipeline.rag_v2 import LectureIndex

DATA_DIR = "data/processed"
VIDEOS = sys.argv[1:] if len(sys.argv) > 1 else ["3OmfTIf-SOU", "VRcixOuG-TU", "oZgbwa8lvDE"]

print("Initialising Gemini Embedding 2...")
svc = EmbeddingService("gemini")

idx = LectureIndex(persist_dir="data/chroma", embedding_model="gemini", _embed_service=svc)

for vid in VIDEOS:
    chunks = json.loads((Path(DATA_DIR) / vid / "transcript/chunks.json").read_text())
    manifest = json.loads((Path(DATA_DIR) / vid / "keyframes/manifest.json").read_text())
    dp = Path(DATA_DIR) / vid / "digest.txt"
    digest = dp.read_text() if dp.exists() else ""

    print(f"\n{vid}: {len(chunks)} chunks, {len(manifest)} keyframes, {len(digest)} chars digest")
    t0 = time.time()
    count = idx.index_video(vid, chunks, manifest, digest)
    print(f"{vid}: indexed {count} items in {time.time()-t0:.1f}s")

print("\nDone (Gemini indexing).")
