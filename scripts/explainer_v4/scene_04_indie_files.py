"""Scene 4 — Indie files everything in the library (~18 s, 0:30–0:48).

Camera pans right to reveal a wall of tiny drawers (the Vector Library).
Indie holds up each item (transcript strip or frame photo); a 1024-dim
coordinate vector floats out and the item slides into a drawer at that
location. Text and image embeddings land in *adjacent* drawers — proving
they share the same space.

Render:
    manim -ql scripts/explainer_v4/scene_04_indie_files.py Scene04IndieFiles
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
    make_indie,
    lower_third_label,
    SpeechBubble,
)
from _shared_library import DrawerWall, vector_arrow_from  # noqa: E402


# 4 items: 2 transcript strips + 2 frame photos.
# Each tuple: (kind, label_text, target_drawer_rc, coord_text)
# Text/frame pairs land in ADJACENT drawers.
ITEMS = [
    ("text",  "[02:10 → 02:20]", (3, 4),  "[ 0.12, -0.44, 0.81, ...]"),
    ("frame", "slide A",          (3, 5),  "[ 0.13, -0.42, 0.79, ...]"),
    ("text",  "[02:30 → 02:40]", (5, 7),  "[-0.31,  0.07, 0.55, ...]"),
    ("frame", "slide C",          (5, 8),  "[-0.30,  0.09, 0.56, ...]"),
]


def _make_text_strip(label: str) -> VGroup:
    rect = RoundedRectangle(
        width=0.95, height=0.40, corner_radius=0.04,
        stroke_color="#A89060", stroke_width=1.0,
        fill_color="#F4E9C9", fill_opacity=0.95,
    )
    # readable transcript snippet instead of squiggles
    snippet = "gradient dir." if "02:10" in label else "loss surface"
    txt = Text(snippet, color="#3A2E18").scale(0.13)
    txt.move_to(rect.get_center() + np.array([0, 0.04, 0]))
    tag = Text(label, color="#7A6238").scale(0.15)
    tag.next_to(rect, DOWN, buff=0.03)
    return VGroup(rect, txt, tag)


def _make_frame_photo(label: str) -> VGroup:
    sq = Square(
        side_length=0.42,
        stroke_color="#9AA8C0", stroke_width=1.0,
        fill_color="#5C7AA8", fill_opacity=0.95,
    )
    inner = Text(label, color=WHITE).scale(0.2)
    inner.move_to(sq.get_center())
    return VGroup(sq, inner)


class Scene04IndieFiles(BaseScene):
    def construct(self):
        # ── lower third ──────────────────────────────────────────
        self.play(
            lower_third_label(
                None,
                "Indexer — Chroma + Jina CLIP v2 (text + image, 1024-dim)",
            )
        )

        # ── camera pans right ────────────────────────────────────
        self.play(
            self.camera.frame.animate.shift(RIGHT * 4),
            run_time=1.0,
        )

        # ── DrawerWall on the right side ────────────────────────
        wall = DrawerWall(n_rows=8, n_cols=12).move_to(np.array([5.5, 0.2, 0]))
        self.play(FadeIn(wall, run_time=0.7))

        # ── Indie enters at the holding-area to the left of wall ─
        hold_pos = np.array([2.4, -0.4, 0])
        indie = make_indie().move_to(hold_pos + np.array([-1.0, 0, 0]))
        self.play(FadeIn(indie, run_time=0.3))
        self.play(indie.animate.move_to(hold_pos), run_time=0.4)

        # ── process the 4 items ─────────────────────────────────
        bubble_shown = False
        for idx, (kind, label, (r, c), coord_text) in enumerate(ITEMS):
            # build the item, place it above Indie
            if kind == "text":
                item = _make_text_strip(label)
            else:
                item = _make_frame_photo(label)
            item.next_to(indie, UP, buff=0.10)
            self.play(FadeIn(item, run_time=0.45))

            # coord vector floats out of the item
            target_drawer = wall.drawer(r, c)
            arrow, coord = vector_arrow_from(
                item, target_drawer, coord_text=coord_text, color=YELLOW,
            )
            self.play(
                FadeIn(coord, run_time=0.40),
                GrowArrow(arrow, run_time=0.75),
            )

            # item slides into the drawer; drawer flashes
            self.play(
                item.animate.scale(0.30).move_to(target_drawer.get_center()),
                run_time=0.75,
            )
            self.play(
                Indicate(target_drawer, color=YELLOW, scale_factor=1.6),
                FadeOut(arrow, run_time=0.35),
                FadeOut(coord, run_time=0.35),
                run_time=0.55,
            )

            # speech bubble after the second item (first text+frame pair done)
            if idx == 1 and not bubble_shown:
                bubble = SpeechBubble("Same space. Text and pixels.", indie, side="left")
                self.play(FadeIn(bubble, run_time=0.25))
                self.wait(0.55)
                self.play(FadeOut(bubble, run_time=0.25))
                bubble_shown = True

        # ── final settle: highlight the adjacent pairs ──────────
        pair_a = VGroup(wall.drawer(3, 4), wall.drawer(3, 5))
        pair_b = VGroup(wall.drawer(5, 7), wall.drawer(5, 8))
        self.play(
            Indicate(pair_a, color=INDIE, scale_factor=1.4),
            Indicate(pair_b, color=INDIE, scale_factor=1.4),
            run_time=1.0,
        )
        self.wait(0.7)
