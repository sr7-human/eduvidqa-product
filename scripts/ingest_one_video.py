"""End-to-end ingest a single YouTube video into pgvector + Supabase Storage.

Mirrors backend/_ingest_video_bg flow but standalone (no API/auth).
Usage: python scripts/ingest_one_video.py <youtube_url_or_id>
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from pipeline.ingest import parse_video_id
from pipeline.keyframes import extract_keyframes
from pipeline.chunking import chunk_transcript
from pipeline.rag import LectureIndex
from backend.supabase_config import get_supabase_client

DATA_DIR = Path("data")
PROCESSED_DIR = DATA_DIR / "processed"


def download_video(video_id: str) -> Path:
    vid_dir = DATA_DIR / "videos" / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    mp4 = vid_dir / f"{video_id}.mp4"
    if mp4.exists():
        print(f"  cached: {mp4}")
        return mp4
    url = f"https://www.youtube.com/watch?v={video_id}"
    import yt_dlp
    ydl_opts = {
        "format": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
        "outtmpl": str(mp4),
        "no_playlist": True,
        "merge_output_format": "mp4",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    if not mp4.exists():
        raise RuntimeError("download failed")
    return mp4


def upload_keyframes(video_id: str, manifest: list[dict]) -> int:
    client = get_supabase_client()
    uploaded = 0
    for kf in manifest:
        local = Path(kf["file"])
        if not local.is_file():
            continue
        remote = f"{video_id}/{kf['frame_id']}.jpg"
        try:
            with open(local, "rb") as f:
                client.storage.from_("keyframes").upload(
                    remote, f, {"content-type": "image/jpeg"}
                )
            uploaded += 1
        except Exception as e:
            err = str(e)
            if "Duplicate" in err or "already exists" in err:
                uploaded += 1
            else:
                print(f"    WARN {kf['frame_id']}: {err[:100]}")
    return uploaded


def main():
    if len(sys.argv) < 2:
        print("usage: ingest_one_video.py <youtube_url_or_id>")
        sys.exit(1)
    arg = sys.argv[1]
    try:
        video_id = parse_video_id(arg)
    except Exception:
        video_id = arg
    print(f"Video: {video_id}")

    index = LectureIndex()
    if index.is_indexed(video_id):
        print("  already indexed in pgvector — only uploading keyframes if needed")
        manifest_path = PROCESSED_DIR / video_id / "keyframes" / "manifest.json"
        if manifest_path.exists():
            mf = json.loads(manifest_path.read_text())
            n = upload_keyframes(video_id, mf)
            print(f"  → {n} keyframes ensured in storage")
        return

    print("Step 1/5: download")
    mp4 = download_video(video_id)

    print("Step 2/5: extract keyframes")
    kf_manifest = extract_keyframes(
        video_path=str(mp4), video_id=video_id, output_dir=str(PROCESSED_DIR)
    )
    print(f"  → {len(kf_manifest)} keyframes")

    print("Step 3/5: chunk transcript")
    chunks = chunk_transcript(
        video_id=video_id,
        output_dir=str(PROCESSED_DIR),
        keyframe_manifest=kf_manifest,
    )
    print(f"  → {len(chunks)} chunks")

    print("Step 4/5: digest (optional)")
    digest = ""
    try:
        from pipeline.digest import generate_digest
        digest = generate_digest(video_id=video_id, data_dir=str(PROCESSED_DIR))
        print(f"  → digest len={len(digest)}")
    except Exception as e:
        print(f"  skip digest: {e}")

    print("Step 5/5: index in pgvector + upload keyframes")
    index.index_video(
        video_id=video_id, chunks=chunks,
        keyframe_manifest=kf_manifest, digest=digest,
    )
    n = upload_keyframes(video_id, kf_manifest)
    print(f"  → {n} keyframes uploaded to Storage")

    # Cleanup mp4
    try:
        shutil.rmtree(DATA_DIR / "videos" / video_id)
    except Exception:
        pass

    print(f"\n✅ Done: {video_id}")


if __name__ == "__main__":
    main()
