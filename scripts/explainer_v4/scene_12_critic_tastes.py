"""Scene 12 — Critic tastes (~12 s, 2:30–2:42).

Critic walks in with a clipboard, takes a tiny bite, and three quality
stamps thump down on the dish edge: Clarity 5/5, ECT 4/5, UPT 5/5.

Render:
    manim -ql scripts/explainer_v4/scene_12_critic_tastes.py Scene12CriticTastes
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    Circle,
    DOWN,
    Ellipse,
    FadeIn,
    Indicate,
    LEFT,
    Line,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Text,
    UP,
    VGroup,
    WHITE,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    SpeechBubble,
    lower_third_label,
    make_critic,
)


GOLD = "#FFD66B"
GREEN = "#7BD389"
AMBER = "#F5B450"


def _make_counter() -> VGroup:
    top = Rectangle(width=10.0, height=0.18,
                    stroke_color=WHITE, stroke_width=1.0,
                    fill_color="#2A2F38", fill_opacity=1)
    top.move_to(np.array([0.0, -1.7, 0]))
    front = Rectangle(width=10.0, height=0.6,
                      stroke_color=WHITE, stroke_width=1.0,
                      fill_color="#1B1F27", fill_opacity=1)
    front.move_to(np.array([0.0, -2.10, 0]))
    return VGroup(front, top)


def _gold_tag(text: str, position) -> VGroup:
    label = Text(text, color=GOLD, weight="BOLD").scale(0.3)
    bg = RoundedRectangle(
        width=label.width + 0.18, height=label.height + 0.10,
        corner_radius=0.05,
        stroke_color=GOLD, stroke_width=1.2,
        fill_color="#1B1F27", fill_opacity=0.85,
    )
    bg.move_to(label.get_center())
    grp = VGroup(bg, label)
    grp.move_to(position)
    return grp


def _make_plated_dish(center) -> VGroup:
    """Recreate the end-state of Scene 11: plate + 4 phrases + 3 gold tags."""
    plate = Ellipse(width=3.6, height=2.4, color=WHITE,
                    stroke_width=2.5, fill_color="#FAFAFA", fill_opacity=0.96)
    plate.move_to(center)

    p1 = Text("The blue arrow at 4:32 shows the negative gradient direction —",
              color="#111").scale(0.24)
    p1.move_to(center + np.array([0.0, 0.55, 0]))
    p2 = Text("the step we'd take to reduce loss", color="#111").scale(0.27)
    p2.move_to(center + np.array([0.0, 0.22, 0]))
    p3 = Text("We negate it for descent.", color="#111").scale(0.27)
    p3.move_to(center + np.array([0.0, -0.10, 0]))
    p4 = Text("The slide at 5:02 shows this as the", color="#111").scale(0.24)
    p4.move_to(center + np.array([0.0, -0.40, 0]))
    p4b = Text("arrow opposite the contour normal.", color="#111").scale(0.24)
    p4b.move_to(center + np.array([0.0, -0.62, 0]))

    tag_a = _gold_tag("[04:30]", center + np.array([-1.30, -0.55, 0]))
    tag_b = _gold_tag("[04:35]", center + np.array([ 1.30, -0.55, 0]))
    tag_c = _gold_tag("[05:02]", center + np.array([ 0.0,  1.15, 0]))

    return VGroup(plate, p1, p2, p3, p4, p4b, tag_a, tag_b, tag_c)


def _make_clipboard() -> VGroup:
    board = RoundedRectangle(
        width=0.55, height=0.75, corner_radius=0.04,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#E8E8E8", fill_opacity=1,
    )
    clip = Rectangle(
        width=0.22, height=0.10,
        stroke_color=WHITE, stroke_width=1.0,
        fill_color="#888", fill_opacity=1,
    ).next_to(board, UP, buff=-0.03)
    line1 = Line(board.get_left() + np.array([0.08, 0.10, 0]),
                 board.get_right() + np.array([-0.08, 0.10, 0]),
                 color="#444", stroke_width=1)
    line2 = Line(board.get_left() + np.array([0.08, -0.05, 0]),
                 board.get_right() + np.array([-0.08, -0.05, 0]),
                 color="#444", stroke_width=1)
    line3 = Line(board.get_left() + np.array([0.08, -0.20, 0]),
                 board.get_right() + np.array([-0.15, -0.20, 0]),
                 color="#444", stroke_width=1)
    return VGroup(board, clip, line1, line2, line3)


def _make_stamp(text: str, border_color: str) -> VGroup:
    label = Text(text, color=border_color, weight="BOLD").scale(0.36)
    bg = RoundedRectangle(
        width=label.width + 0.30, height=label.height + 0.22,
        corner_radius=0.06,
        stroke_color=border_color, stroke_width=2.5,
        fill_color="#FAFAFA", fill_opacity=0.95,
    )
    label.move_to(bg.get_center())
    return VGroup(bg, label)


class Scene12CriticTastes(BaseScene):
    def construct(self):
        # ── Counter + plated dish (Scene 11 end-state) ─────────────
        counter = _make_counter()
        self.add(counter)

        plate_center = np.array([0.5, 0.30, 0])
        dish = _make_plated_dish(plate_center)
        self.add(dish)
        self.wait(0.4)

        # ── Critic enters from screen-left holding a clipboard ────
        critic = make_critic()
        critic.move_to(np.array([-7.0, -1.05, 0]))
        clipboard = _make_clipboard()
        critic.hold_prop(clipboard)
        self.play(FadeIn(critic, run_time=0.3))
        self.play(critic.animate.move_to(np.array([-2.6, -1.05, 0])), run_time=1.2)

        self.play(lower_third_label(critic, "Judge — Llama 3.3 70B · LLM-as-judge"))

        # ── Tiny bite: a transparent "PASS" stamp instead of black circle ─
        pass_label = Text("PASS", color="#4ADE80", weight="BOLD").scale(0.40)
        pass_border = RoundedRectangle(
            width=pass_label.width + 0.30, height=pass_label.height + 0.20,
            corner_radius=0.06,
            stroke_color="#4ADE80", stroke_width=3.0,
            fill_opacity=0,
        )
        pass_border.move_to(pass_label.get_center())
        bite = VGroup(pass_border, pass_label)
        bite.move_to(plate_center + np.array([-1.20, -0.10, 0]))
        self.play(FadeIn(bite, scale=1.5, run_time=0.5))
        self.play(Indicate(bite, color="#4ADE80", scale_factor=1.1, run_time=0.4))
        self.wait(0.5)

        # ── 3 stamps — Clarity (green), ECT (amber), UPT (green) ──
        stamp_y = plate_center[1] - 1.40  # below the plate
        clarity = _make_stamp("Clarity 5/5", GREEN)
        ect     = _make_stamp("ECT 4/5",     AMBER)
        upt     = _make_stamp("UPT 5/5",     GREEN)

        clarity.move_to(np.array([-1.7, stamp_y, 0]))
        ect.move_to    (np.array([ 0.5, stamp_y, 0]))
        upt.move_to    (np.array([ 2.7, stamp_y, 0]))

        # Clarity stamp: drop + thump
        self.play(FadeIn(clarity, scale=1.6, run_time=0.4))
        self.play(Indicate(clarity, scale_factor=1.15, run_time=0.4))
        self.wait(0.2)

        # ECT stamp
        self.play(FadeIn(ect, scale=1.6, run_time=0.4))
        self.play(Indicate(ect, scale_factor=1.15, run_time=0.4))
        self.wait(0.2)

        # UPT stamp
        self.play(FadeIn(upt, scale=1.6, run_time=0.4))
        self.play(Indicate(upt, scale_factor=1.15, run_time=0.4))
        self.wait(0.3)

        # ── Critic bubble ─────────────────────────────────────────
        bubble = SpeechBubble("Cited. Grounded. Approved.", anchor=critic, side="right")
        bubble.show(self, duration=1.6)

        self.wait(1.2)
