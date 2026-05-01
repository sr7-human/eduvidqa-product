"""Scene 8 — Indie embeds + retrieves (~22 s, 1:18–1:40).

Indie reads the order ticket. The question text lifts off as glowing letters,
condenses into a glowing arrow + 1024-d coordinate, and Indie walks the arrow
into the Vector Library wall, opening one drawer. A tray rises out of the
drawer holding 10 transcript scrolls + 3 photo frames, each tagged with a
similarity score.

Render:
    manim -ql scripts/explainer_v4/scene_08_indie_retrieves.py Scene08IndieRetrieves
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    FadeIn,
    FadeOut,
    GrowArrow,
    Indicate,
    LEFT,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Square,
    Text,
    Transform,
    UP,
    VGroup,
    WHITE,
    YELLOW,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    INDIE,
    OrderTicket,
    make_indie,
    SpeechBubble,
)
from _shared_library import DrawerWall, vector_arrow_from  # noqa: E402


# 10 transcript scrolls + 3 photos with descending similarity scores
SIM_SCORES = [0.74, 0.71, 0.69, 0.66, 0.64, 0.62, 0.60, 0.58, 0.56, 0.55]
PHOTO_SCORES = [0.72, 0.68, 0.61]


_SCROLL_SNIPPETS = [
    "gradient dir.",
    "blue arrow",
    "loss function",
    "contour line",
    "negative step",
    "vector field",
    "tangent plane",
    "descent path",
    "learning rate",
    "convex optim.",
]
_SCROLL_IDX = 0


def _mini_scroll() -> VGroup:
    global _SCROLL_IDX
    rect = RoundedRectangle(
        width=0.55, height=0.22, corner_radius=0.03,
        stroke_color="#A89060", stroke_width=0.8,
        fill_color="#F4E9C9", fill_opacity=0.95,
    )
    snippet = _SCROLL_SNIPPETS[_SCROLL_IDX % len(_SCROLL_SNIPPETS)]
    _SCROLL_IDX += 1
    line = Text(snippet, color="#3A2E18").scale(0.12)
    line.move_to(rect.get_center())
    return VGroup(rect, line)


def _mini_photo() -> VGroup:
    sq = Square(
        side_length=0.32,
        stroke_color="#9AA8C0", stroke_width=0.8,
        fill_color="#5C7AA8", fill_opacity=0.95,
    )
    return VGroup(sq)


class Scene08IndieRetrieves(BaseScene):
    def construct(self):
        # ── DrawerWall on the right ──────────────────────────────
        wall = DrawerWall(n_rows=5, n_cols=6).move_to(np.array([2.5, 0.2, 0]))
        self.play(FadeIn(wall, run_time=1.0))

        # ── Indie holding the order ticket on the left ──────────
        indie = make_indie().move_to(np.array([-3.2, -0.6, 0]))
        ticket = OrderTicket(
            question="What does the blue arrow at 4:32 mean?",
            timestamp="04:32",
            video_id="3OmfTIf-SOU",
        )
        ticket.scale(0.95).next_to(indie, UP, buff=0.10)
        self.play(FadeIn(indie, run_time=0.6), FadeIn(ticket, run_time=0.9))
        self.wait(1.4)  # Indie "reads silently"

        # ── question text lifts off as glowing letters ──────────
        glow = Text("What does the blue arrow at 4:32 mean?", color=YELLOW).scale(0.42)
        glow.move_to(ticket.get_center() + np.array([0, 0.05, 0]))
        self.play(FadeIn(glow, run_time=0.6))
        self.play(
            glow.animate.move_to(np.array([-1.4, 0.6, 0])).scale(1.05),
            run_time=1.4,
        )

        # ── condense letters into an arrow + coord label ────────
        target_drawer = wall.drawer(3, 4)
        arrow, coord = vector_arrow_from(
            glow, target_drawer,
            coord_text="[ 0.31, -0.07, 0.49, ...]",
            color=YELLOW,
        )
        # show arrow growing while letters fade out
        self.play(
            FadeOut(glow, run_time=0.8),
            GrowArrow(arrow, run_time=1.6),
            FadeIn(coord, run_time=1.0),
        )
        self.wait(0.7)

        # ── Indie walks the arrow toward the wall ───────────────
        self.play(
            indie.animate.move_to(np.array([0.0, -0.6, 0])),
            ticket.animate.move_to(np.array([0.0, 0.5, 0])).scale(0.7),
            run_time=2.0,
        )

        # ── highlight target drawer + slide it open ─────────────
        self.play(Indicate(target_drawer, color=YELLOW, scale_factor=1.6, run_time=0.9))

        open_offset = np.array([0.45, 0, 0])
        self.play(
            target_drawer.animate.shift(open_offset).set_fill(opacity=0.4),
            run_time=1.1,
        )

        # ── fade out the arrow + coord (their job is done) ──────
        self.play(
            FadeOut(arrow, run_time=0.5),
            FadeOut(coord, run_time=0.5),
        )

        # ── tray rises out of the drawer with 10 scrolls + 3 photos
        tray_w = 5.6
        tray_h = 1.9
        tray = RoundedRectangle(
            width=tray_w, height=tray_h, corner_radius=0.10,
            stroke_color="#C0C8D8", stroke_width=1.5,
            fill_color="#1B1F27", fill_opacity=0.92,
        )
        tray.move_to(target_drawer.get_center() + np.array([0, 0, 0]))
        tray.set_opacity(0.0)

        # build scrolls (2 rows × 5) on the upper portion of the tray
        scrolls: list[VGroup] = []
        for k in range(10):
            r = k // 5
            c = k % 5
            s = _mini_scroll()
            cx = tray.get_center()[0] + (c - 2) * 0.66
            cy = tray.get_center()[1] + 0.50 - r * 0.42
            s.move_to(np.array([cx, cy, 0]))
            scrolls.append(s)

        # build 3 photos on the bottom row of the tray
        photos: list[VGroup] = []
        for k in range(3):
            p = _mini_photo()
            cx = tray.get_center()[0] + (k - 1) * 0.45
            cy = tray.get_center()[1] - 0.55
            p.move_to(np.array([cx, cy, 0]))
            photos.append(p)

        items = VGroup(*scrolls, *photos)
        items.set_opacity(0.0)

        # rise: shift tray + items upward 1 unit while fading in
        rise_target = target_drawer.get_center() + np.array([0, 1.4, 0])
        self.play(
            tray.animate.move_to(rise_target).set_opacity(0.92),
            *[s.animate.shift(np.array([0, 1.4, 0])).set_opacity(1.0) for s in scrolls],
            *[p.animate.shift(np.array([0, 1.4, 0])).set_opacity(1.0) for p in photos],
            run_time=2.8,
        )

        # ── fade in similarity scores beside each item ──────────
        score_labels: list[Text] = []
        for s, val in zip(scrolls, SIM_SCORES):
            t = Text(f"{val:.2f}", color="#FFD27F").scale(0.2)
            t.next_to(s, DOWN, buff=0.04)
            score_labels.append(t)
        for p, val in zip(photos, PHOTO_SCORES):
            t = Text(f"{val:.2f}", color="#FFD27F").scale(0.2)
            t.next_to(p, DOWN, buff=0.04)
            score_labels.append(t)

        self.play(
            *[FadeIn(t, run_time=1.5) for t in score_labels],
            run_time=1.5,
        )
        self.wait(1.0)

        # ── Indie says "Top 10. Plus three frames." ─────────────
        bubble = SpeechBubble("Top 10. Plus three frames.", indie, side="left")
        self.play(FadeIn(bubble, run_time=0.30))
        self.wait(1.1)
        self.play(FadeOut(bubble, run_time=0.30))

        # ── final beat ──────────────────────────────────────────
        self.play(
            Indicate(VGroup(tray, items), color=INDIE, scale_factor=1.04),
            run_time=1.0,
        )
        self.wait(1.2)
