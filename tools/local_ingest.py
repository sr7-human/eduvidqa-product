"""Local admin ingest — run the full pipeline from your Mac (residential IP).

Importable core used by the Streamlit app (`tools/ingest_app.py`) and usable
standalone. Ingests a single video OR an entire playlist into the SAME
production database, so results appear globally in the live app.

Why local? YouTube blocks the Hugging Face Space's datacenter IP. Your home
IP is not blocked, so running here is reliable.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env", override=True)

import psycopg2  # noqa: E402

from pipeline.ingest import parse_video_id  # noqa: E402
from pipeline.keyframes import extract_keyframes  # noqa: E402
from pipeline.chunking import chunk_transcript  # noqa: E402
from pipeline.rag import LectureIndex  # noqa: E402
from backend.supabase_config import get_supabase_client  # noqa: E402

DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"


def _db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def downloads_size_mb() -> float:
    """Total size (MB) of the downloaded-video cache in data/videos/."""
    total = 0
    vids = DATA_DIR / "videos"
    if vids.exists():
        for p in vids.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except Exception:
                    pass
    return total / (1024 * 1024)


def clear_downloads() -> float:
    """Delete all downloaded videos (re-downloadable cache). Returns MB freed."""
    freed = downloads_size_mb()
    vids = DATA_DIR / "videos"
    if vids.exists():
        for child in vids.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except Exception:
                pass
    return freed


def resolve_admin_user_id() -> str | None:
    """First email in ADMIN_EMAILS → its user UUID (from auth.users)."""
    emails = [e.strip() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]
    if not emails:
        return None
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM auth.users WHERE email = ANY(%s) LIMIT 1", (emails,))
            row = cur.fetchone()
        return str(row[0]) if row else None
    except Exception:
        return None


def is_playlist(url: str) -> bool:
    import re

    return bool(re.search(r"[?&]list=", url))


def expand_playlist(url: str) -> list[str]:
    """Return the list of video IDs in a playlist URL (flat — no download)."""
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = info.get("entries") or []
    return [e["id"] for e in entries if e.get("id")]


def _download_video(video_id: str, log) -> Path:
    vid_dir = DATA_DIR / "videos" / video_id
    vid_dir.mkdir(parents=True, exist_ok=True)
    mp4 = vid_dir / f"{video_id}.mp4"
    if mp4.exists():
        log("  (using cached download)")
        return mp4
    import yt_dlp

    ydl_opts = {
        "format": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best",
        "outtmpl": str(mp4),
        "no_playlist": True,
        "merge_output_format": "mp4",
        "quiet": True,
        "extractor_args": {"youtube": {"player_client": ["web", "default", "android", "ios"]}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    if not mp4.exists():
        raise RuntimeError("download failed (no file produced)")
    return mp4


def _upload_keyframes(video_id: str, manifest: list[dict]) -> int:
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
            if "Duplicate" in str(e) or "already exists" in str(e):
                uploaded += 1
    return uploaded


def _set_title_and_link(video_id: str, user_id: str | None) -> str:
    title, channel = video_id, None
    try:
        u = (
            "https://www.youtube.com/oembed?url="
            + urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}")
            + "&format=json"
        )
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(req, timeout=8))
        title = d.get("title") or video_id
        channel = d.get("author_name")
    except Exception:
        pass
    with _db() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET title=%s, channel_name=%s, updated_at=now() WHERE video_id=%s",
                (title, channel, video_id),
            )
            if user_id:
                cur.execute(
                    "INSERT INTO user_videos (id,user_id,video_id,last_watched_at) "
                    "VALUES (%s,%s,%s,now()) ON CONFLICT (user_id,video_id) "
                    "DO UPDATE SET last_watched_at=now()",
                    (str(uuid.uuid4()), user_id, video_id),
                )
    return title


def ingest_one(url_or_id: str, user_id: str | None = None, log=print) -> dict:
    """Ingest one video end-to-end into production. Returns a result dict.

    Idempotent: if the video is already indexed it is skipped (only re-links +
    ensures keyframes) — this is what makes playlist **resume** work: just run
    the same playlist again and completed videos are skipped.
    """
    try:
        video_id = parse_video_id(url_or_id)
    except Exception:
        video_id = url_or_id
    result = {"video_id": video_id, "status": "", "title": video_id,
              "chunks": 0, "keyframes": 0, "error": None, "skipped": False}
    try:
        index = LectureIndex()
        if index.is_indexed(video_id):
            log("already ingested — skipping (ensuring library link)")
            mpath = PROCESSED_DIR / video_id / "keyframes" / "manifest.json"
            if mpath.exists():
                _upload_keyframes(video_id, json.loads(mpath.read_text()))
            title = _set_title_and_link(video_id, user_id)
            result.update(status="ready", title=title, skipped=True)
            return result

        log("1/5 download"); mp4 = _download_video(video_id, log)
        log("2/5 keyframes")
        kf = extract_keyframes(video_path=str(mp4), video_id=video_id, output_dir=str(PROCESSED_DIR))
        log(f"  → {len(kf)} keyframes")
        log("3/5 transcript")
        chunks = chunk_transcript(video_id=video_id, output_dir=str(PROCESSED_DIR), keyframe_manifest=kf)
        log(f"  → {len(chunks)} chunks")
        log("4/5 digest")
        digest = ""
        try:
            from pipeline.digest import generate_digest

            digest = generate_digest(video_id=video_id, data_dir=str(PROCESSED_DIR))
        except Exception as e:
            log(f"  digest skipped: {str(e)[:80]}")
        log("5/5 index + upload")
        index.index_video(video_id=video_id, chunks=chunks, keyframe_manifest=kf, digest=digest)
        n = _upload_keyframes(video_id, kf)
        title = _set_title_and_link(video_id, user_id)
        try:
            shutil.rmtree(DATA_DIR / "videos" / video_id)
        except Exception:
            pass
        result.update(status="ready", title=title, chunks=len(chunks), keyframes=n)
        log(f"✅ Done: {title}")
        return result
    except Exception as e:
        log(f"❌ Failed: {str(e)[:150]}")
        result.update(status="failed", error=str(e)[:300])
        return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python tools/local_ingest.py <youtube_url_or_playlist_url>")
        sys.exit(1)
    uid = resolve_admin_user_id()
    target = sys.argv[1]
    if is_playlist(target):
        vids = expand_playlist(target)
        print(f"Playlist: {len(vids)} videos")
        for i, v in enumerate(vids, 1):
            print(f"\n=== [{i}/{len(vids)}] {v} ===")
            ingest_one(v, uid)
    else:
        ingest_one(target, uid)
