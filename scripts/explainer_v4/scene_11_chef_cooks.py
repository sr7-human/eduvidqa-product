"""Scene 11 — Chef Vee cooks (~25 s, 2:05–2:30).

Tray arrives at the kitchen counter. Chef Vee dons two-lens glasses
(text + vision), spreads ingredients, looks back and forth, lights the
wok, and an answer plates itself onto a white dish phrase by phrase
with gold citation tags `[mm:ss]` landing as garnish on the rim.

Render:
    manim -ql scripts/explainer_v4/scene_11_chef_cooks.py Scene11ChefCooks
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    AddTextLetterByLetter,
    Circle,
    DOWN,
    Ellipse,
    FadeIn,
    FadeOut,
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

# allow `from explainer_v4_lib import …` when run via `manim` from repo root
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    SpeechBubble,
    lower_third_label,
    make_vee,
)


GOLD = "#FFD66B"
WOK_DARK = "#2A2F38"
WOK_HOT = "#FF7A1A"


def _make_glasses() -> VGroup:
    """Two-lens 'multimodal' glasses — left lens 'T' (text), right lens frame (vision)."""
    left_ring = Circle(radius=0.18, color=WHITE, stroke_width=2)
    left_ring.move_to(np.array([-0.20, 0.0, 0]))
    t_glyph = Text("T", color=WHITE, weight="BOLD").scale(0.33)
    t_glyph.move_to(left_ring.get_center())

    right_ring = Circle(radius=0.18, color=WHITE, stroke_width=2)
    right_ring.move_to(np.array([0.20, 0.0, 0]))
    # tiny "picture frame" inside right lens
    frame_outer = RoundedRectangle(
        width=0.22, height=0.16, corner_radius=0.02,
        stroke_color=WHITE, stroke_width=1.4, fill_opacity=0,
    ).move_to(right_ring.get_center())
    pic_dot = Circle(radius=0.025, color=WHITE, fill_opacity=1, stroke_width=0)
    pic_dot.move_to(right_ring.get_center() + np.array([-0.05, 0.0, 0]))
    pic_tri = Line(
        right_ring.get_center() + np.array([0.0, -0.04, 0]),
        right_ring.get_center() + np.array([0.07, 0.04, 0]),
        color=WHITE, stroke_width=1.2,
    )

    bridge = Line(
        left_ring.get_right(), right_ring.get_left(),
        color=WHITE, stroke_width=1.5,
    )
    return VGroup(left_ring, t_glyph, right_ring, frame_outer, pic_dot, pic_tri, bridge)


def _make_wok(center) -> VGroup:
    bowl = Ellipse(width=1.2, height=0.45, color=WHITE, stroke_width=2,
                   fill_color=WOK_DARK, fill_opacity=1)
    bowl.move_to(center)
    handle = Line(
        bowl.get_right(), bowl.get_right() + np.array([0.55, 0.10, 0]),
        color=WHITE, stroke_width=2,
    )
    return VGroup(bowl, handle)


def _make_scroll(center) -> VGroup:
    body = RoundedRectangle(
        width=0.55, height=0.32, corner_radius=0.04,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#F2EAD3", fill_opacity=1,
    )
    body.move_to(center)
    line1 = Line(body.get_left() + np.array([0.07, 0.06, 0]),
                 body.get_right() + np.array([-0.07, 0.06, 0]),
                 color="#777", stroke_width=1)
    line2 = Line(body.get_left() + np.array([0.07, -0.02, 0]),
                 body.get_right() + np.array([-0.07, -0.02, 0]),
                 color="#777", stroke_width=1)
    line3 = Line(body.get_left() + np.array([0.07, -0.10, 0]),
                 body.get_right() + np.array([-0.10, -0.10, 0]),
                 color="#777", stroke_width=1)
    return VGroup(body, line1, line2, line3)


def _make_photo(center) -> VGroup:
    frame = Rectangle(
        width=0.45, height=0.34,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#3A3F4B", fill_opacity=1,
    )
    frame.move_to(center)
    sun = Circle(radius=0.05, color="#FFD66B", fill_opacity=1, stroke_width=0)
    sun.move_to(frame.get_center() + np.array([-0.10, 0.06, 0]))
    horizon = Line(
        frame.get_left() + np.array([0.04, -0.04, 0]),
        frame.get_right() + np.array([-0.04, -0.04, 0]),
        color="#A8C8FF", stroke_width=1.2,
    )
    return VGroup(frame, sun, horizon)


def _make_tray(center) -> VGroup:
    tray = RoundedRectangle(
        width=2.1, height=1.2, corner_radius=0.10,
        stroke_color=WHITE, stroke_width=1.4,
        fill_color="#1B1F27", fill_opacity=1,
    )
    tray.move_to(center)
    # 3 scrolls + 2 photos abstracted on top
    s1 = _make_scroll(center + np.array([-0.65,  0.22, 0]))
    s2 = _make_scroll(center + np.array([ 0.00,  0.22, 0]))
    s3 = _make_scroll(center + np.array([ 0.65,  0.22, 0]))
    p1 = _make_photo (center + np.array([-0.35, -0.25, 0]))
    p2 = _make_photo (center + np.array([ 0.35, -0.25, 0]))
    return VGroup(tray, s1, s2, s3, p1, p2)


def _make_counter() -> VGroup:
    """Kitchen counter: a long flat surface across the bottom-center."""
    top = Rectangle(
        width=10.0, height=0.18,
        stroke_color=WHITE, stroke_width=1.0,
        fill_color="#2A2F38", fill_opacity=1,
    )
    top.move_to(np.array([0.0, -1.7, 0]))
    front = Rectangle(
        width=10.0, height=0.6,
        stroke_color=WHITE, stroke_width=1.0,
        fill_color="#1B1F27", fill_opacity=1,
    )
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


class Scene11ChefCooks(BaseScene):
    def construct(self):
        # ── Counter + Vee on the right ────────────────────────────
        counter = _make_counter()
        self.add(counter)

        vee = make_vee()
        vee.move_to(np.array([3.5, 0.2, 0]))
        self.play(FadeIn(vee, run_time=0.4))

        self.play(lower_third_label(vee, "VLM — Groq Llama-4 Scout (vision-language)"))

        # ── Tray slides in from the left and lands on the counter ─
        tray = _make_tray(np.array([-7.5, -1.05, 0]))
        self.add(tray)
        self.play(tray.animate.move_to(np.array([-3.4, -1.05, 0])), run_time=1.2)

        # ── Glasses fly in and land on Vee's face ─────────────────
        glasses = _make_glasses()
        glasses.move_to(np.array([3.5, 2.5, 0]))
        self.play(FadeIn(glasses, run_time=0.5))
        self.play(
            glasses.animate.move_to(vee.get_center() + np.array([0.0, 0.10, 0])),
            run_time=1.5,
        )
        self.wait(0.5)

        bubble1 = SpeechBubble("Reading text. And pixels.", anchor=vee, side="left")
        bubble1.show(self, duration=2.5)

        # ── Spread ingredients across the counter (fan out) ───────
        scroll_a = _make_scroll(np.array([-3.4, -0.95, 0]))
        scroll_b = _make_scroll(np.array([-2.4, -0.95, 0]))
        scroll_c = _make_scroll(np.array([-1.4, -0.95, 0]))
        photo_a  = _make_photo (np.array([-2.9, -1.50, 0]))
        photo_b  = _make_photo (np.array([-1.9, -1.50, 0]))
        spread = VGroup(scroll_a, scroll_b, scroll_c, photo_a, photo_b)
        self.play(FadeIn(spread, scale=0.7, run_time=0.6))

        # ── Look pattern: scroll → photo → scroll (eye-line dot) ──
        eye_dot = Circle(radius=0.06, color=GOLD, fill_opacity=1, stroke_width=0)
        eye_dot.move_to(vee.get_center() + np.array([-0.05, 0.10, 0]))
        self.play(FadeIn(eye_dot, run_time=0.2))
        self.play(eye_dot.animate.move_to(scroll_a.get_center()), run_time=0.55)
        self.play(eye_dot.animate.move_to(photo_a.get_center()),  run_time=0.55)
        self.play(eye_dot.animate.move_to(scroll_c.get_center()), run_time=0.55)
        self.wait(0.3)
        self.play(FadeOut(eye_dot, run_time=0.2))

        # ── Wok lights up ─────────────────────────────────────────
        wok = _make_wok(np.array([2.6, -1.30, 0]))
        self.play(FadeIn(wok, run_time=0.4))
        flame = Ellipse(width=0.9, height=0.35, color=WOK_HOT,
                        fill_color=WOK_HOT, fill_opacity=0.0, stroke_width=0)
        flame.move_to(wok.get_center() + np.array([0.0, 0.05, 0]))
        self.add(flame)
        self.play(flame.animate.set_fill(WOK_HOT, opacity=0.85), run_time=0.5)

        # ── fade out flame before plate so it never overlaps ──────
        self.play(FadeOut(flame, run_time=0.3))

        # ── Plate appears at center counter (ABOVE wok/flame layer) ─
        plate = Ellipse(width=3.6, height=2.4, color=WHITE,
                        stroke_width=2.5, fill_color="#FAFAFA", fill_opacity=0.96)
        plate.move_to(np.array([0.0, 0.80, 0]))
        self.play(FadeIn(plate, scale=0.8, run_time=0.5))

        # ── Progressive plating: per-phrase AddTextLetterByLetter ──
        # Phrase positions stacked vertically inside the plate.
        plate_center = plate.get_center()
        phrase1 = Text(
            "The blue arrow at 4:32 shows the negative gradient direction —",
            color="#111",
        ).scale(0.22)
        phrase1.move_to(plate_center + np.array([0.0, 0.45, 0]))
        phrase1.set_z_index(10)

        phrase2 = Text(
            "the step we'd take to reduce loss",
            color="#111",
        ).scale(0.24)
        phrase2.move_to(plate_center + np.array([0.0, 0.16, 0]))
        phrase2.set_z_index(10)

        phrase3 = Text(
            "Compare it to the red arrow she drew at 2:15",
            color="#111",
        ).scale(0.22)
        phrase3.move_to(plate_center + np.array([0.0, -0.10, 0]))
        phrase3.set_z_index(10)

        phrase4 = Text(
            "— same idea, opposite sign on",
            color="#111",
        ).scale(0.22)
        phrase4.move_to(plate_center + np.array([0.0, -0.32, 0]))
        phrase4b = Text(
            "the loss surface",
            color="#111",
        ).scale(0.22)
        phrase4b.move_to(plate_center + np.array([0.0, -0.50, 0]))
        phrase4.set_z_index(10)
        phrase4b.set_z_index(10)

        # gold tag positions on the rim (8, 4, 12 o'clock)
        rim_8 = plate_center + np.array([-1.10, -0.40, 0])
        rim_4 = plate_center + np.array([ 1.10, -0.40, 0])
        rim_12 = plate_center + np.array([ 0.0,  0.95, 0])

        tag_0432 = _gold_tag("[04:32]", rim_8)
        tag_0215 = _gold_tag("[02:15]", rim_4)
        tag_0502 = _gold_tag("[05:02]", rim_12)

        # Phrase 1 (no tag yet)
        self.play(AddTextLetterByLetter(phrase1, run_time=2.2))

        # Phrase 2 + drop [04:32]
        self.play(AddTextLetterByLetter(phrase2, run_time=1.6))
        self.play(FadeIn(tag_0432, scale=1.4, run_time=0.5))

        # Phrase 3 + drop [02:15]
        self.play(AddTextLetterByLetter(phrase3, run_time=1.6))
        self.play(FadeIn(tag_0215, scale=1.4, run_time=0.5))

        # Phrase 4 (two-line) + drop [05:02]
        self.play(AddTextLetterByLetter(phrase4, run_time=1.8))
        self.play(AddTextLetterByLetter(phrase4b, run_time=1.6))
        self.play(FadeIn(tag_0502, scale=1.4, run_time=0.5))

        # ── Hold on the finished dish ─────────────────────────────
        self.wait(2.6)
