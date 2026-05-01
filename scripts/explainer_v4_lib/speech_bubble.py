"""Speech bubbles + lower-third caption helpers."""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    RIGHT,
    RoundedRectangle,
    Succession,
    Text,
    VGroup,
    WHITE,
)


_MAX_WORDS = 5


class SpeechBubble(VGroup):
    """Tiny bubble next to a character. Hard cap of 5 words."""

    def __init__(self, text: str, anchor, side: str = "right", **kwargs):
        super().__init__(**kwargs)
        words = text.split()
        if len(words) > _MAX_WORDS:
            raise ValueError(
                f"SpeechBubble text must be ≤ {_MAX_WORDS} words; got {len(words)}: {text!r}"
            )

        label = Text(text, color="#111").scale(0.34)
        pad_w = max(label.width + 0.40, 1.1)
        pad_h = label.height + 0.36
        bubble = RoundedRectangle(
            width=pad_w,
            height=pad_h,
            corner_radius=0.10,
            stroke_color=WHITE,
            stroke_width=1.2,
            fill_color=WHITE,
            fill_opacity=0.95,
        )
        label.move_to(bubble.get_center())
        self.add(bubble, label)

        # position next to anchor
        offset = RIGHT * 1.0 if side == "right" else LEFT * 1.0
        try:
            anchor_point = anchor.get_center()
        except AttributeError:
            anchor_point = np.array(anchor)
        self.move_to(anchor_point + offset + np.array([0, 0.85, 0]))

    def show(self, scene, duration: float = 1.0):
        scene.play(FadeIn(self, run_time=0.4))
        scene.wait(max(duration - 0.8, 0.0))
        scene.play(FadeOut(self, run_time=0.4))


def lower_third_label(character, label_text: str):
    """Slide a tiny caption across bottom-left for 2 s, then exit."""
    cap_text = Text(label_text, color=WHITE).scale(0.48)
    bg = RoundedRectangle(
        width=cap_text.width + 0.6,
        height=cap_text.height + 0.30,
        corner_radius=0.08,
        stroke_color=WHITE,
        stroke_width=1.0,
        fill_color="#1B1F27",
        fill_opacity=0.9,
    )
    cap_text.move_to(bg.get_center())
    group = VGroup(bg, cap_text)

    # bottom-left of standard 14×8 frame, slide in from off-screen left
    final_pos = np.array([-5.0, -3.6, 0])
    group.move_to(final_pos + LEFT * 6)

    return Succession(
        FadeIn(group, shift=RIGHT * 6, run_time=0.4),
        group.animate.shift(np.array([0, 0, 0])).set_run_time(1.2),
        FadeOut(group, shift=LEFT * 2, run_time=0.4),
    )
