"""Scene 15 — Curtain Call (~15 s).

Wide shot of the restaurant facade. All six characters line up in front,
small wave staggered left → right. Big "EduVidQA" sign above. URL
`eduvidqa.app` fades in beneath. Maitre says "Bring a lecture."

Render:
    manim -ql scripts/explainer_v4/scene_15_curtain_call.py Scene15CurtainCall
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    FadeIn,
    FadeOut,
    Line,
    Rectangle,
    Text,
    UP,
    VGroup,
    WHITE,
    Wiggle,
)

# allow `from explainer_v4_lib import …` when run via `manim` from repo root
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    SpeechBubble,
    make_critic,
    make_indie,
    make_lens,
    make_maitre,
    make_quill,
    make_vee,
)


GOLD = "#FFD66B"
URL_TEXT = "eduvidqa.app"


def _make_facade() -> VGroup:
    """A simple restaurant-facade silhouette behind the line-up."""
    wall = Rectangle(
        width=12.0, height=3.0,
        stroke_color="#5A6172", stroke_width=1.5,
        fill_color="#1B1F27", fill_opacity=1,
    )
    wall.move_to(np.array([0, 1.2, 0]))

    # door at center
    door = Rectangle(
        width=1.2, height=1.8,
        stroke_color="#5A6172", stroke_width=1.5,
        fill_color="#0F141B", fill_opacity=1,
    )
    door.move_to(np.array([0, -0.1, 0]))

    # ground line in front of facade
    ground = Line(
        np.array([-7.0, -1.45, 0]),
        np.array([ 7.0, -1.45, 0]),
        stroke_color="#3A3F4B", stroke_width=1.5,
    )
    return VGroup(wall, door, ground)


class Scene15CurtainCall(BaseScene):
    def construct(self):
        self.wait(0.3)

        # ── 1. Big title at top ───────────────────────────────────
        sign = Text("EduVidQA", color=WHITE, weight="BOLD").scale(1.8)
        sign.move_to(np.array([0, 2.2, 0]))
        self.play(FadeIn(sign, shift=DOWN * 0.3, run_time=0.9))

        # ── 2. line up all 6 characters across the middle ────────
        chars = [
            make_maitre(),
            make_quill(),
            make_lens(),
            make_indie(),
            make_vee(),
            make_critic(),
        ]
        xs = np.linspace(-4.5, 4.5, len(chars))
        for ch, x in zip(chars, xs):
            ch.move_to(np.array([x, -0.2, 0]))

        line_up = VGroup(*chars)
        self.play(FadeIn(line_up, shift=UP * 0.3, run_time=0.9))
        self.wait(0.3)

        # ── 3. Role labels for each agent ─────────────────────────
        roles = ["API Router", "Transcriber", "Frame Scanner",
                 "Vector Indexer", "Vision LLM", "Quality Judge"]
        role_labels = VGroup()
        for ch, role in zip(chars, roles):
            rl = Text(role, color=GOLD).scale(0.32)
            rl.next_to(ch, DOWN, buff=0.65)
            role_labels.add(rl)
        self.play(FadeIn(role_labels, run_time=0.7))
        self.wait(1.0)

        # ── 4. staggered wave, left → right ───────────────────────
        for ch in chars:
            self.play(Wiggle(ch, scale_value=1.1, n_wiggles=3, run_time=0.45))

        # ── 5. URL beneath title, in gold ─────────────────────────
        url = Text(URL_TEXT, color=GOLD).scale(0.75)
        url.next_to(sign, DOWN, buff=0.3)
        self.play(FadeIn(url, run_time=0.9))

        # ── 6. hold the final frame ──────────────────────────────
        self.wait(3.5)

        self.play(
            FadeOut(VGroup(sign, url, line_up, role_labels), run_time=0.6),
        )
