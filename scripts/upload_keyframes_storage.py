"""Upload local keyframe JPEGs to Supabase Storage bucket 'keyframes'."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from backend.supabase_config import get_supabase_client

PROCESSED_DIR = Path("data/processed")


def upload_for_video(video_id: str, client) -> int:
    kf_dir = PROCESSED_DIR / video_id / "keyframes"
    manifest_path = kf_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"  SKIP: no manifest.json")
        return 0

    manifest = json.loads(manifest_path.read_text())
    uploaded = 0
    for kf in manifest:
        local_file = Path(kf["file"])
        if not local_file.is_file():
            continue
        remote_path = f"{video_id}/{kf['frame_id']}.jpg"
        try:
            with open(local_file, "rb") as f:
                client.storage.from_("keyframes").upload(
                    remote_path, f, {"content-type": "image/jpeg"}
                )
            uploaded += 1
        except Exception as e:
            err = str(e)
            if "Duplicate" in err or "already exists" in err:
                uploaded += 1
            else:
                print(f"    WARN {kf['frame_id']}: {err[:80]}")
    return uploaded


def main():
    client = get_supabase_client()
    video_dirs = sorted([
        d.name for d in PROCESSED_DIR.iterdir()
        if d.is_dir() and (d / "keyframes").exists()
    ])

    total = 0
    for vid in video_dirs:
        print(f"Uploading keyframes for {vid}...")
        n = upload_for_video(vid, client)
        print(f"  → {n} keyframes uploaded")
        total += n

    print(f"\nTotal: {total} keyframes uploaded to Supabase Storage.")


if __name__ == "__main__":
    main()
