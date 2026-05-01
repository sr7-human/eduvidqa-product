"""Scene 3 — Lens picks keyframes (~12 s, 0:18–0:30).

Lens walks the frame strip with an "SSIM" magnifying glass. Adjacent frames
that look the same are crumpled into a discard bin; new slides snap onto the
corkboard. One speech bubble appears: "Same slide. Skip."

Render:
    manim -ql scripts/explainer_v4/scene_03_lens_keyframes.py Scene03LensKeyframes
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    Annulus,
    Circle,
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
    LENS,
    make_lens,
    lower_third_label,
    SpeechBubble,
)
from _shared_library import Corkboard  # noqa: E402


# 8 frames: 5 distinct slides interleaved with 3 duplicates.
# Tag each frame with which "slide" it is. Adjacent same → duplicate.
FRAME_PLAN = [
    ("A", False),  # 0  new — pin
    ("A", True),   # 1  dup — discard
    ("B", False),  # 2  new — pin
    ("C", False),  # 3  new — pin
    ("C", True),   # 4  dup — discard
    ("D", False),  # 5  new — pin
    ("D", True),   # 6  dup — discard  (Lens speaks here)
    ("E", False),  # 7  new — pin
]

SLIDE_COLORS = {
    "A": "#5C7AA8",
    "B": "#A87A5C",
    "C": "#5CA87A",
    "D": "#A85C9A",
    "E": "#9AA85C",
}

FRAME_SIDE = 0.55


def _make_frame(slide: str) -> VGroup:
    sq = Square(
        side_length=FRAME_SIDE,
        stroke_color="#9AA8C0", stroke_width=1.0,
        fill_color=SLIDE_COLORS[slide], fill_opacity=0.95,
    )
    tag = Text(slide, color=WHITE).scale(0.27)
    tag.move_to(sq.get_center())
    return VGroup(sq, tag)


def _make_magnifier() -> VGroup:
    ring = Annulus(
        inner_radius=0.22, outer_radius=0.30,
        color="#E0E5EE", fill_opacity=0.4, stroke_width=1.5,
    )
    handle = Line(
        np.array([0.20, -0.20, 0]),
        np.array([0.50, -0.50, 0]),
        stroke_color="#C0C8D8", stroke_width=4,
    )
    label = Text("SSIM", color=LENS).scale(0.24)
    label.next_to(ring, UP, buff=0.05)
    return VGroup(ring, handle, label)


class Scene03LensKeyframes(BaseScene):
    def construct(self):
        # ── lower third ──────────────────────────────────────────
        self.play(
            lower_third_label(None, "Lens — Keyframe extractor · SSIM dedup")
        )

        # ── frame strip across the top ──────────────────────────
        strip_y = 1.6
        gap = FRAME_SIDE + 0.20
        total_w = (len(FRAME_PLAN) - 1) * gap
        frames: list[VGroup] = []
        for i, (slide, _dup) in enumerate(FRAME_PLAN):
            f = _make_frame(slide)
            f.move_to(np.array([-total_w / 2 + i * gap, strip_y, 0]))
            frames.append(f)
        strip_group = VGroup(*frames)
        self.play(FadeIn(strip_group, run_time=0.5))

        # ── corkboard (left) and discard bin (right) ────────────
        board = Corkboard(rows=2, cols=3).scale(0.85).move_to(np.array([-3.7, -0.6, 0]))
        bin_box = RoundedRectangle(
            width=1.6, height=1.0, corner_radius=0.12,
            stroke_color="#FF8A8A", stroke_width=1.5,
            fill_color="#3A1A1A", fill_opacity=0.85,
        ).move_to(np.array([4.2, -0.6, 0]))
        bin_label = Text("0.92 similarity → discard", color="#FFB0B0").scale(0.27)
        bin_label.next_to(bin_box, DOWN, buff=0.10)
        self.play(
            FadeIn(board, run_time=0.4),
            FadeIn(bin_box, run_time=0.4),
            FadeIn(bin_label, run_time=0.4),
        )

        # ── Lens with magnifier walks the strip ─────────────────
        lens = make_lens().move_to(np.array([-total_w / 2 - 0.8, 0.6, 0]))
        magnifier = _make_magnifier().scale(0.9).next_to(lens, UP, buff=0.05)
        lens_group = VGroup(lens, magnifier)
        self.play(FadeIn(lens_group, run_time=0.3))

        # corkboard fill order — only NEW frames pin
        new_targets = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]
        new_idx = 0
        bubble_shown = False

        for i, (slide, is_dup) in enumerate(FRAME_PLAN):
            target_frame = frames[i]
            # lens walks above this frame + quick comparing indicate
            self.play(
                lens_group.animate.move_to(
                    target_frame.get_center() + np.array([0, 1.0, 0])
                ),
                Indicate(target_frame, color=LENS, scale_factor=1.15),
                run_time=0.42,
            )

            if is_dup:
                # "Same slide. Skip." bubble on the first duplicate.
                if not bubble_shown:
                    bubble = SpeechBubble("Same slide. Skip.", lens, side="right")
                    self.play(FadeIn(bubble, run_time=0.20))
                    self.wait(0.30)
                    self.play(FadeOut(bubble, run_time=0.18))
                    bubble_shown = True
                # discard: shrink + send to bin
                self.play(
                    target_frame.animate
                    .scale(0.4)
                    .move_to(bin_box.get_center())
                    .set_opacity(0.5),
                    run_time=0.55,
                )
            else:
                # pin to corkboard
                r, c = new_targets[new_idx]
                new_idx += 1
                target_pos = board.slot_position(r, c)
                # ensure frame renders in front of the board it pins onto
                target_frame.set_z_index(5)
                self.play(
                    target_frame.animate.scale(0.85).move_to(target_pos),
                    run_time=0.55,
                )

        self.wait(0.5)
