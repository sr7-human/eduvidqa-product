"""Scene 1 — Cold Open (~8 s).

Pitch black → neon sign flickers on → floorplan dim behind →
delivery truck rolls in, drops `lecture.mp4` → sign brightens.

Render:
    manim -ql scripts/explainer_v4/scene_01_cold_open.py Scene01ColdOpen
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    Circle,
    FadeIn,
    FadeOut,
    LEFT,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Text,
    UP,
    VGroup,
    WHITE,
)

# allow `from explainer_v4_lib import …` when run via `manim` from repo root
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import BaseScene, RestaurantFloorplan  # noqa: E402


SIGN_COLOR = "#FF6B9D"


def _make_truck() -> VGroup:
    body = Rectangle(
        width=1.6, height=0.7,
        stroke_color=WHITE, stroke_width=1.5,
        fill_color="#3A3F4B", fill_opacity=1,
    )
    cab = Rectangle(
        width=0.55, height=0.55,
        stroke_color=WHITE, stroke_width=1.5,
        fill_color="#2A2F38", fill_opacity=1,
    )
    cab.next_to(body, RIGHT, buff=0).align_to(body, UP)
    wheel_l = Circle(radius=0.16, color="#111", fill_opacity=1, stroke_width=1)
    wheel_r = Circle(radius=0.16, color="#111", fill_opacity=1, stroke_width=1)
    wheel_l.move_to(body.get_corner(LEFT + UP) + np.array([0.35, -0.85, 0]))
    wheel_r.move_to(cab.get_corner(RIGHT + UP) + np.array([-0.20, -0.85, 0]))
    return VGroup(body, cab, wheel_l, wheel_r)


def _make_canister() -> VGroup:
    box = RoundedRectangle(
        width=1.6, height=0.7,
        corner_radius=0.06,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#222831", fill_opacity=1,
    )
    label = Text("lecture.mp4", color=WHITE).scale(0.24)
    label.move_to(box.get_center())
    return VGroup(box, label)


class Scene01ColdOpen(BaseScene):
    def construct(self):
        # ── 0.3 s of black ────────────────────────────────────────
        self.wait(0.3)

        # ── floorplan, dim ────────────────────────────────────────
        floor = RestaurantFloorplan().set_opacity(0.30)
        self.play(FadeIn(floor, run_time=0.5))

        # ── neon sign (starts dim, flickers, then fades to 60 %) ──
        sign = Text(
            "EduVidQA — Open Kitchen",
            color=SIGN_COLOR,
            weight="BOLD",
        ).scale(0.85)
        sign.move_to(np.array([0, 2.6, 0]))

        sign.set_opacity(0.0)
        self.add(sign)

        # 3 quick blinks
        for opacity in (0.85, 0.0, 0.95, 0.0, 0.60):
            self.play(sign.animate.set_opacity(opacity), run_time=0.18)

        # ── truck rolls in, drops canister, exits ─────────────────
        truck = _make_truck()
        truck.move_to(np.array([-8.0, -2.3, 0]))
        self.play(FadeIn(truck, run_time=0.2))
        self.play(
            truck.animate.move_to(np.array([-2.5, -2.3, 0])),
            run_time=1.4,
        )

        canister = _make_canister()
        canister.move_to(truck.get_center() + np.array([-0.2, 0.0, 0]))
        self.play(FadeIn(canister, scale=0.6, run_time=0.35))

        # drop to floor (back-door area, just left of pantry)
        drop_target = np.array([-3.4, -2.85, 0])
        self.play(canister.animate.move_to(drop_target), run_time=0.55)

        # truck continues, exits screen-right
        self.play(
            truck.animate.move_to(np.array([8.5, -2.3, 0])),
            run_time=1.3,
        )

        # ── sign brightens to full ────────────────────────────────
        self.play(sign.animate.set_opacity(1.0), run_time=0.6)
        self.wait(0.7)

        # graceful end
        self.play(
            FadeOut(VGroup(sign, floor, canister), run_time=0.5),
        )
