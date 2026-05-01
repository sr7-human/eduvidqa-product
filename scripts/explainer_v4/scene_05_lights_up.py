"""Scene 5 — Lights up (~7 s, 0:48–0:55).

Sign flips Closed → Now Serving. Maitre walks in, ties apron, mini-bow.

Render:
    manim -ql scripts/explainer_v4/scene_05_lights_up.py Scene05LightsUp
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    RIGHT,
    Text,
    Transform,
    UP,
    VGroup,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import BaseScene, RestaurantFloorplan, make_customer, make_maitre  # noqa: E402


SIGN_COLOR_LIVE = "#7CFFB2"


class Scene05LightsUp(BaseScene):
    def construct(self):
        # ── floorplan at full opacity (transition out of Act-I dim) ──
        floor = RestaurantFloorplan()
        self.play(FadeIn(floor, run_time=0.6))

        # ── headline: index built, system is live ──────────────────
        title = Text("Index built  \u2192  ready to answer questions",
                     color=SIGN_COLOR_LIVE, weight="BOLD").scale(0.55)
        title.move_to(np.array([0, 2.6, 0]))
        self.play(FadeIn(title, run_time=0.5))

        # ── student walks up to the kitchen ────────────────────────
        student = make_customer().scale(0.9)
        student.move_to(np.array([-7.0, -2.05, 0]))
        self.add(student)
        self.play(student.animate.move_to(np.array([-2.2, -2.05, 0])), run_time=1.4)

        # ── "Ask any question" prompt floats up between student and kitchen ──
        prompt = Text("Ask any question  \u2192", color="#FFD27F", weight="BOLD").scale(0.50)
        prompt.move_to(np.array([0.0, -0.4, 0]))
        self.play(FadeIn(prompt, shift=UP * 0.3), run_time=0.6)

        # ── maitre appears at the kitchen window, ready to take orders ──
        maitre = make_maitre()
        maitre.move_to(np.array([3.5, -2.05, 0]))
        self.play(FadeIn(maitre, run_time=0.5))
        # tiny nod
        self.play(maitre.animate.scale(0.9), run_time=0.25)
        self.play(maitre.animate.scale(1.0 / 0.9), run_time=0.25)

        # ── hold so viewer registers the beat ──────────────────────
        self.wait(2.4)

        self.remove(floor, title, student, prompt, maitre)
