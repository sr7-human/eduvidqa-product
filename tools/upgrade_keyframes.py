"""Upgrade an EXISTING video's stored keyframes to higher resolution (720p),
without re-ingesting (embeddings, chunks, checkpoints and quizzes are untouched).

How it works:
  1. Read the video's keyframe timestamps from the DB.
  2. Download the video once at 720p (with the same cookie auth as ingest).
  3. Re-extract each keyframe at 720p and OVERWRITE the same Supabase Storage
     object (upsert) — so the public URL stays identical but the image is now
     high-res and readable.

Only the *displayed* image improves; the semantic embedding (used for matching)
is left as-is, which is fine — matching works on low-res too; readability is
about the image the answer model sees.

Usage:
  .venv/bin/python tools/upgrade_keyframes.py <video_id> [--limit N]

Tip: try a SHORT video first (e.g. the 20-frame SVM clip Q7vT0--5VII) before the
7-hour one (2,705 frames ≈ a big download + many uploads).
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")


def _load_env() -> None:
    for line in Path(".env").read_text().splitlines():
        for k in ("DATABASE_URL", "GEMINI_API_KEY", "GROQ_API_KEY",
                  "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
                  "YOUTUBE_COOKIES_FROM_BROWSER", "YOUTUBE_COOKIES_B64", "YOUTUBE_COOKIES"):
            if line.startswith(k + "="):
                os.environ[k] = line.split("=", 1)[1].strip().strip('"')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N keyframes (0 = all)")
    args = ap.parse_args()

    _load_env()
    import cv2
    import psycopg2
    import yt_dlp
    from pipeline.ingest import get_cookie_ydl_opts
    from pipeline.storage import upload_keyframe

    vid = args.video_id

    # 1. Existing keyframe timestamps.
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute(
            "SELECT timestamp_seconds FROM keyframe_embeddings WHERE video_id=%s ORDER BY timestamp_seconds",
            (vid,),
        )
        tss = [int(r[0]) for r in cur.fetchall()]
    conn.close()
    if not tss:
        print("no keyframes for", vid)
        return
    if args.limit:
        tss = tss[: args.limit]
    print(f"{vid}: {len(tss)} keyframes to upgrade")

    # 2. Download the video at 720p.
    tmp = Path(tempfile.mkdtemp(prefix="eduvidqa-upgrade-"))
    video_path = tmp / f"{vid}.mp4"
    print("downloading 720p video …")
    ydl_opts = {
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "outtmpl": str(video_path),
        "no_playlist": True,
        "merge_output_format": "mp4",
        "quiet": True,
        **get_cookie_ydl_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={vid}"])
    real = next((p for p in tmp.glob(f"{vid}.*")), None)
    if real is None or not real.is_file():
        print("download failed")
        return

    cap = cv2.VideoCapture(str(real))
    if not cap.isOpened():
        print("cannot open downloaded video")
        return
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    Hh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"downloaded {W}x{Hh}; re-extracting + uploading …")

    done = 0
    for ts in tss:
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        name = f"kf_{ts:06d}.jpg"
        out_p = tmp / name
        cv2.imwrite(str(out_p), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        url = upload_keyframe(vid, {"file": str(out_p), "frame_id": f"kf_{ts:06d}"})
        out_p.unlink(missing_ok=True)
        done += 1
        if done % 25 == 0 or done == len(tss):
            print(f"  {done}/{len(tss)}  (last url ok: {bool(url)})")
    cap.release()
    print(f"done: upgraded {done} keyframes to {W}x{Hh}")


if __name__ == "__main__":
    main()
