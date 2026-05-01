"""Scene 2 — Quill chunks the transcript (~10 s, 0:08–0:18).

Quill walks in carrying the lecture canister, unrolls it into a ribbon of
transcript text with a parallel strip of video frames, then snips the ribbon
every 10 seconds. Each pair (text + frame) drops into a tray, stamped with
its [mm:ss → mm:ss] window.

Render:
    manim -ql scripts/explainer_v4/scene_02_quill_chunks.py Scene02QuillChunks
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    FadeIn,
    FadeOut,
    Indicate,
    LEFT,
    Line,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Square,
    Text,
    UP,
    VGroup,
    WHITE,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    QUILL,
    make_quill,
    lower_third_label,
)


N_CHUNKS = 6
CHUNK_W = 1.30
CHUNK_H = 0.45
FRAME_SIDE = 0.50

CHUNK_FILL = "#F4E9C9"  # parchment
FRAME_FILL = "#2A2F3A"
TRAY_FILL = "#1B1F27"


def _make_canister() -> VGroup:
    box = RoundedRectangle(
        width=1.8, height=0.8,
        corner_radius=0.06,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#222831", fill_opacity=1,
    )
    label = Text("lecture transcript", color=WHITE).scale(0.26)
    label.move_to(box.get_center())
    return VGroup(box, label)


def _stamp_text(start_s: int, end_s: int) -> Text:
    s_mm = f"{start_s // 60:02d}:{start_s % 60:02d}"
    e_mm = f"{end_s // 60:02d}:{end_s % 60:02d}"
    return Text(f"[{s_mm} → {e_mm}]", color="#FFD27F").scale(0.24)


class Scene02QuillChunks(BaseScene):
    def construct(self):
        # ── lower third ───────────────────────────────────────────
        self.play(
            lower_third_label(None, "Scribe — Transcript chunker · pipeline/chunking.py")
        )

        # ── Quill enters from screen-left holding canister ───────
        quill = make_quill().move_to(np.array([-6.0, -1.5, 0]))
        canister = _make_canister()
        canister.scale(0.8).next_to(quill, UP, buff=0.05)
        quill_group = VGroup(quill, canister)

        self.play(FadeIn(quill_group, run_time=0.3))
        self.play(
            quill_group.animate.move_to(np.array([-4.5, -1.0, 0])),
            run_time=0.7,
        )

        # ── unroll: canister becomes ribbon + frame strip ────────
        ribbon_y = -0.6
        frames_y = 0.15
        total_w = N_CHUNKS * CHUNK_W

        # short readable phrases per chunk so viewer sees "text being chopped"
        snippets = [
            "\u201cToday we'll cover\u2026\u201d",
            "\u201cthe blue arrow shows\u2026\u201d",
            "\u201call quantities flow\u2026\u201d",
            "\u201cnotice at four-thirty-two\u2026\u201d",
            "\u201cthe vector points\u2026\u201d",
            "\u201cnext, recall that\u2026\u201d",
        ]

        chunks: list[Rectangle] = []
        frames: list[Square] = []
        for i in range(N_CHUNKS):
            cx = -total_w / 2 + (i + 0.5) * CHUNK_W
            chunk = Rectangle(
                width=CHUNK_W * 0.96, height=CHUNK_H,
                stroke_color="#A89060", stroke_width=1.2,
                fill_color=CHUNK_FILL, fill_opacity=0.95,
            ).move_to(np.array([cx, ribbon_y, 0]))
            # readable transcript snippet inside chunk
            squiggle = Text(snippets[i], color="#3A2E18").scale(0.18)
            squiggle.move_to(chunk.get_center())
            chunks.append(VGroup(chunk, squiggle))

            frame = Square(
                side_length=FRAME_SIDE,
                stroke_color="#9AA8C0", stroke_width=1.0,
                fill_color=FRAME_FILL, fill_opacity=0.95,
            ).move_to(np.array([cx, frames_y, 0]))
            frames.append(frame)

        ribbon_group = VGroup(*chunks, *frames)
        self.play(
            FadeOut(canister, run_time=0.25),
            FadeIn(ribbon_group, run_time=0.7),
        )

        # ── tray below to catch snipped pieces ───────────────────
        tray = Rectangle(
            width=total_w + 0.4, height=0.55,
            stroke_color="#7A8090", stroke_width=1.2,
            fill_color=TRAY_FILL, fill_opacity=0.85,
        ).move_to(np.array([0, -2.4, 0]))
        tray_label = Text("chunks/", color="#C0C8D8").scale(0.27)
        tray_label.next_to(tray, RIGHT, buff=0.15)
        self.play(FadeIn(VGroup(tray, tray_label), run_time=0.3))

        # ── 5 snip-and-drop animations ───────────────────────────
        # snip happens between chunk i and chunk i+1. The chunk that "falls"
        # into the tray is chunk i (and frame i), stamped with its window.
        for i in range(5):
            # vertical scissor indicator between chunk i and chunk i+1
            x_cut = chunks[i][0].get_right()[0] + 0.02
            cut_line = Line(
                np.array([x_cut, frames_y + 0.40, 0]),
                np.array([x_cut, ribbon_y - 0.30, 0]),
                stroke_color="#FF6B6B", stroke_width=2.5,
            )
            self.play(FadeIn(cut_line, run_time=0.12))
            self.play(FadeOut(cut_line, run_time=0.12))

            # build stamp for this 10-second window starting at 02:10
            base = 130  # 02:10
            stamp = _stamp_text(base + i * 10, base + (i + 1) * 10)

            # drop chunk i + frame i into the tray, stamp appears alongside
            piece = VGroup(chunks[i], frames[i])
            tray_x = tray.get_left()[0] + 0.5 + i * (CHUNK_W * 0.85)
            target = np.array([tray_x, tray.get_center()[1] + 0.05, 0])
            stamp.move_to(target + np.array([0, -0.38, 0]))

            self.play(
                piece.animate.scale(0.55).move_to(target),
                FadeIn(stamp, run_time=0.45),
                run_time=0.55,
            )

        # ── small settle ─────────────────────────────────────────
        self.play(Indicate(tray, color=QUILL, scale_factor=1.04, run_time=0.6))
        self.wait(1.4)
