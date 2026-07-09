"""Resumable quiz regeneration for a single video.

Generates quizzes for every checkpoint that is not already cached, in small
groups, caching immediately after each group so progress survives interruption.

Usage:
    python -m tools.regen_quizzes <video_id> [--count 7] [--group 4] [--openrouter]
"""
from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

load_dotenv(".env", override=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--count", type=int, default=7)
    ap.add_argument("--group", type=int, default=4)
    ap.add_argument("--openrouter", action="store_true",
                    help="Force OpenRouter (skip Gemini/Groq free tiers)")
    ap.add_argument("--vision", action="store_true",
                    help="Lecture mode: ground quizzes in on-screen keyframes "
                         "(loads data/processed/<vid>/keyframes/manifest.json)")
    args = ap.parse_args()

    if args.openrouter:
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.setdefault("QUIZ_LLM_MIN_INTERVAL", "1")

    import psycopg2

    from pipeline.quiz_gen import generate_quizzes_for_checkpoints
    from pipeline.quiz_cache import cache_questions, get_cached_questions

    vid = args.video_id
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT chunk_id,text,start_time,end_time FROM video_chunks "
        "WHERE video_id=%s ORDER BY start_time", (vid,))
    chunks = [{"chunk_id": r[0], "text": r[1], "start_time": r[2], "end_time": r[3]}
              for r in cur.fetchall()]
    cur.execute(
        "SELECT timestamp_seconds FROM checkpoints WHERE video_id=%s "
        "ORDER BY timestamp_seconds", (vid,))
    cps = [float(r[0]) for r in cur.fetchall()]
    cur.close()
    conn.close()

    todo = [ts for ts in cps if not get_cached_questions(vid, int(ts // 30), 1)]

    keyframes = None
    if args.vision:
        import json
        from pathlib import Path
        manifest = Path("data/processed") / vid / "keyframes" / "manifest.json"
        if manifest.is_file():
            keyframes = json.loads(manifest.read_text())
            print(f"[regen] vision: loaded {len(keyframes)} keyframes", flush=True)
        else:
            print(f"[regen] vision requested but no manifest at {manifest} — "
                  "falling back to transcript-only", flush=True)

    print(f"[regen] {vid}: {len(cps)} checkpoints, {len(todo)} to generate, "
          f"{len(chunks)} chunks, count={args.count}, "
          f"vision={bool(keyframes)}", flush=True)

    t0 = time.time()
    cached_total = 0
    for i in range(0, len(todo), args.group):
        group = todo[i:i + args.group]
        try:
            res = generate_quizzes_for_checkpoints(vid, group, chunks,
                                                   count_per_cp=args.count,
                                                   keyframes=keyframes)
        except Exception as exc:  # noqa: BLE001
            print(f"[regen] group {group} failed: {str(exc)[:160]}", flush=True)
            continue
        for ts, qs in res.items():
            if qs:
                cache_questions(vid, int(ts // 30), 1, qs)
                cached_total += len(qs)
        done = min(i + args.group, len(todo))
        print(f"[regen] {done}/{len(todo)} checkpoints done, "
              f"{cached_total} questions cached, {time.time() - t0:.0f}s elapsed",
              flush=True)

    print(f"[regen] DONE: {cached_total} questions cached in "
          f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
