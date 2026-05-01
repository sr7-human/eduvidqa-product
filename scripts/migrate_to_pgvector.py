"""One-time migration: embed & insert existing processed videos into Supabase pgvector."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from pipeline.rag import LectureIndex

PROCESSED_DIR = Path("data/processed")


def migrate_video(video_id: str, index: LectureIndex) -> bool:
    vid_dir = PROCESSED_DIR / video_id

    chunks_path = vid_dir / "transcript" / "chunks.json"
    if not chunks_path.exists():
        print(f"  SKIP: no chunks.json")
        return False
    chunks = json.loads(chunks_path.read_text())

    manifest_path = vid_dir / "keyframes" / "manifest.json"
    keyframes = json.loads(manifest_path.read_text()) if manifest_path.exists() else []

    digest = ""
    digest_path = vid_dir / "digest.txt"
    if digest_path.exists():
        digest = digest_path.read_text().strip()

    total = index.index_video(video_id=video_id, chunks=chunks,
                               keyframe_manifest=keyframes, digest=digest)
    print(f"  ✓ {total} items indexed ({len(chunks)} chunks + {len(keyframes)} keyframes)")
    return True


def main():
    index = LectureIndex()

    video_dirs = sorted([
        d.name for d in PROCESSED_DIR.iterdir()
        if d.is_dir() and (d / "transcript").exists()
    ])
    print(f"Found {len(video_dirs)} videos to migrate: {video_dirs}\n")

    success = 0
    for vid in video_dirs:
        print(f"Migrating {vid}...")
        if index.is_indexed(vid):
            print(f"  SKIP: already indexed")
            success += 1
            continue
        try:
            if migrate_video(vid, index):
                success += 1
        except Exception as e:
            print(f"  FAIL: {e}")

    print(f"\nDone: {success}/{len(video_dirs)} videos migrated.")


if __name__ == "__main__":
    main()
