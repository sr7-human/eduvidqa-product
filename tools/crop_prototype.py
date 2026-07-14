"""Prototype: crop a lecture keyframe down to its CONTENT region (whiteboard /
blackboard / slide / the text-bearing area), cutting out the room, the
professor and the students.

Approach A (classical CV, no new deps): find where the "writing" is via a text
region recipe (morphological gradient -> Otsu -> horizontal close -> contours),
take the union bounding box of text-like blocks, pad it, and crop. Falls back to
the full frame when it can't confidently find content.

Run:  .venv/bin/python tools/crop_prototype.py
Writes originals + crops into  /tmp/eduvidqa-crop-proto/
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, ".")

OUT = Path("/tmp/eduvidqa-crop-proto")
OUT.mkdir(exist_ok=True)


def _load_env() -> None:
    for line in Path(".env").read_text().splitlines():
        for k in ("DATABASE_URL", "GEMINI_API_KEY"):
            if line.startswith(k + "="):
                os.environ[k] = line.split("=", 1)[1].strip().strip('"')


def content_crop(img: np.ndarray, pad_frac: float = 0.02) -> tuple[np.ndarray, tuple[int, int, int, int] | None, float]:
    """Return (cropped_img, bbox_or_None, coverage_fraction).

    coverage_fraction = area(bbox) / area(frame). If we can't find a confident
    content region, returns the original frame and bbox=None.
    """
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Morphological gradient highlights strokes/edges (text, chalk, ink).
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)

    # 2. Binarize (Otsu) -> where there's "ink".
    _, bw = cv2.threshold(grad, 0.0, 255.0, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # 3. Close horizontally to merge characters into words/lines/blocks.
    close_k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, W // 40), 1))
    connected = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, close_k)
    # A little vertical close to merge lines into a block.
    connected = cv2.morphologyEx(
        connected, cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(5, H // 60))),
    )

    # 4. Contours -> keep text-like blocks (reasonable size, not full-frame noise).
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = float(W * H)
    boxes: list[tuple[int, int, int, int]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < frame_area * 0.0008:        # too tiny (noise / single speck)
            continue
        if area > frame_area * 0.9:            # basically the whole frame
            continue
        ar = w / max(1, h)
        fill = cv2.contourArea(c) / max(1, area)
        # text blocks are wide-ish and reasonably filled; skip thin lines / borders
        if h < 6 or w < 12:
            continue
        if fill < 0.15:
            continue
        boxes.append((x, y, x + w, y + h))

    if not boxes:
        return img, None, 1.0

    xs0 = min(b[0] for b in boxes)
    ys0 = min(b[1] for b in boxes)
    xs1 = max(b[2] for b in boxes)
    ys1 = max(b[3] for b in boxes)

    # 5. Pad a touch so we don't clip strokes.
    px, py = int(W * pad_frac), int(H * pad_frac)
    x0 = max(0, xs0 - px)
    y0 = max(0, ys0 - py)
    x1 = min(W, xs1 + px)
    y1 = min(H, ys1 + py)

    coverage = ((x1 - x0) * (y1 - y0)) / frame_area

    # 6. Sanity: if the crop is basically the whole frame, or absurdly small,
    # keep the original (avoids bad crops on talking-head / low-signal frames).
    if coverage > 0.92 or coverage < 0.04:
        return img, None, coverage

    return img[y0:y1, x0:x1], (x0, y0, x1, y1), coverage


def main() -> None:
    _load_env()
    import psycopg2
    dsn = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        # Grab keyframes spread across the video.
        cur.execute(
            """
            SELECT timestamp_seconds, storage_path
            FROM keyframe_embeddings
            WHERE video_id = %s
            ORDER BY timestamp_seconds
            """,
            ("Vfo5le26IhY",),
        )
        rows = cur.fetchall()
    conn.close()
    if not rows:
        print("no keyframes found")
        return

    # Pick ~5 evenly spaced frames.
    picks = [rows[int(i * (len(rows) - 1) / 4)] for i in range(5)]

    for idx, (ts, url) in enumerate(picks):
        if not url.startswith("http"):
            continue
        try:
            data = urllib.request.urlopen(url, timeout=15).read()
        except Exception as exc:
            print(f"[{idx}] download failed: {exc}")
            continue
        arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            continue
        cropped, bbox, cov = content_crop(arr)
        orig_p = OUT / f"{idx}_t{int(ts)}_orig.jpg"
        crop_p = OUT / f"{idx}_t{int(ts)}_crop.jpg"
        cv2.imwrite(str(orig_p), arr)
        cv2.imwrite(str(crop_p), cropped)
        mm, ss = divmod(int(ts), 60)
        hh, mm = divmod(mm, 60)
        status = "CROPPED" if bbox else "kept full (no confident content)"
        print(f"[{idx}] {hh:d}:{mm:02d}:{ss:02d}  {arr.shape[1]}x{arr.shape[0]} -> "
              f"{cropped.shape[1]}x{cropped.shape[0]}  coverage={cov:.0%}  {status}")
        print(f"      orig: {orig_p}")
        print(f"      crop: {crop_p}")


if __name__ == "__main__":
    main()
