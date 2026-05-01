"""Scene 10 — The fresh catch / live frame (~13 s, 1:52–2:05).

Maitre detours past the frosted-glass freezer door labeled `cached .mp4`,
opens it, pulls out a photo card stamped `t = 04:32 (exact)`, and slides
it to the front of the tray. Then hands the tray off toward the kitchen.

Ticket continuity:
    TICKET_START = np.array([2.4, -1.2, 0])    # = end of Scene 9
    TICKET_END   = np.array([4.5, -1.6, 0])    # handing off toward kitchen counter

Render:
    manim -ql scripts/explainer_v4/scene_10_live_frame.py Scene10LiveFrame
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
from manim import (
    Dot,
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    PI,
    RIGHT,
    Rectangle,
    Rotate,
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
    OrderTicket,
    RestaurantFloorplan,
    SpeechBubble,
    lower_third_label,
    make_maitre,
)


TICKET_START = np.array([2.4, -1.2, 0])
TICKET_END = np.array([4.5, -1.6, 0])


def _make_mini_tray() -> VGroup:
    """A small simplified tray (visual placeholder)."""
    frame = Rectangle(
        width=1.4, height=1.6,
        stroke_color=WHITE, stroke_width=1.0,
        fill_color="#1B1F27", fill_opacity=0.5,
    )
    items = VGroup()
    for i in range(4):
        items.add(RoundedRectangle(
            width=1.1, height=0.22, corner_radius=0.04,
            stroke_color=WHITE, stroke_width=0.8,
            fill_color="#E8DCC2", fill_opacity=0.85,
        ).move_to(np.array([0.0, 0.55 - i * 0.32, 0])))
    return VGroup(frame, items)


def _make_freezer(width: float = 1.6, height: float = 2.6) -> VGroup:
    door = RoundedRectangle(
        width=width, height=height, corner_radius=0.08,
        stroke_color="#4A8A9A", stroke_width=2.0,
        fill_color="#0F2A35", fill_opacity=1.0,
    )
    label = Text("FRAME CACHE", color="#8AC8E0", weight="BOLD").scale(0.30)
    label.move_to(door.get_center() + np.array([0, 0.95, 0]))
    sublabel = Text("(original video)", color="#6BA8C0").scale(0.20)
    sublabel.next_to(label, DOWN, buff=0.05)
    handle = Rectangle(
        width=0.06, height=0.45,
        stroke_width=0, fill_color="#888", fill_opacity=1,
    ).move_to(door.get_corner(RIGHT) + np.array([-0.10, 0, 0]))
    return VGroup(door, label, sublabel, handle)


class Scene10LiveFrame(BaseScene):
    def construct(self):
        # ── floorplan + ticket from Scene 9 ─────────────────────────
        floor = RestaurantFloorplan()
        self.add(floor)

        ticket = OrderTicket(
            question="What does the blue arrow at 4:32 mean?",
            timestamp="04:32",
            video_id="3OmfTIf-SOU",
        )
        ticket.scale(0.7).move_to(TICKET_START)
        self.add(ticket)

        # ── tray (with ticket on top) ───────────────────────────────
        tray = _make_mini_tray()
        tray.move_to(np.array([1.6, -1.0, 0]))
        self.play(FadeIn(tray, run_time=0.4))
        # ticket sits on top of tray
        self.play(ticket.animate.move_to(tray.get_top() + np.array([0, 0.18, 0])), run_time=0.3)

        # ── maitre enters carrying tray (visually: walks up to it) ──
        maitre = make_maitre()
        maitre.move_to(np.array([-2.5, -2.05, 0]))
        self.play(FadeIn(maitre, run_time=0.4))
        # walk to tray
        self.play(
            maitre.animate.move_to(np.array([0.7, -2.05, 0])),
            run_time=0.8,
            rate_func=lambda t: t,
        )

        # ── lower-third label (process tag) ─────────────────────────
        # runs in parallel with the detour to freezer
        # ── caption explaining the detour ──────────────────────────
        caption = Text(
            "Need the exact slide? Pull a frame from the original video.",
            color="#FFD27F",
        ).scale(0.34)
        caption.move_to(np.array([0.5, 2.6, 0]))
        self.play(FadeIn(caption, run_time=0.5))

        # ── frame cache cabinet ────────────────────────────────────
        freezer = _make_freezer()
        freezer.move_to(np.array([-4.5, 0.5, 0]))
        self.play(FadeIn(freezer, run_time=0.4))

        # detour: maitre + tray + ticket move toward freezer
        detour_pt = np.array([-3.4, -2.05, 0])
        self.play(
            maitre.animate.move_to(detour_pt),
            tray.animate.shift(detour_pt - np.array([0.7, -2.05, 0])),
            ticket.animate.shift(detour_pt - np.array([0.7, -2.05, 0])),
            lower_third_label(maitre, "live_frame.py — exact-second capture from cached video"),
            run_time=1.5,
        )

        # ── door opens (rotate hinge) ───────────────────────────────
        door = freezer[0]   # the RoundedRectangle
        # rotate door around its left edge
        hinge = door.get_corner(LEFT)
        self.play(door.animate.shift(RIGHT * 1.2).set_opacity(0.3), run_time=0.8)

        # ── frosty mist ─────────────────────────────────────────────
        mist = VGroup()
        rng = random.Random(7)
        for _ in range(14):
            d = Dot(
                point=freezer.get_center() + np.array([
                    rng.uniform(-0.3, 0.3),
                    rng.uniform(-0.3, 0.3),
                    0,
                ]),
                radius=rng.uniform(0.05, 0.10),
                color="#8AC8E0",
            ).set_opacity(rng.uniform(0.3, 0.6))
            mist.add(d)
        self.play(FadeIn(mist, run_time=0.3))
        self.play(
            mist.animate.shift(UP * 0.6 + RIGHT * 0.4).set_opacity(0.0),
            run_time=0.6,
        )

        # ── pull out the photo card ─────────────────────────────────
        card = VGroup(
            RoundedRectangle(
                width=1.5, height=0.7, corner_radius=0.06,
                stroke_color=WHITE, stroke_width=1.2,
                fill_color="#1A3A4A", fill_opacity=1.0,
            ),
            Text("t = 04:32", color=WHITE).scale(0.24),
        )
        card[1].move_to(card[0].get_center())
        card.move_to(freezer.get_center())
        self.play(FadeIn(card, run_time=0.3))
        # carry card to the tray's front
        self.play(card.animate.move_to(tray.get_center() + np.array([0, 0.65, 0])), run_time=0.8)

        # ── speech bubble: "Fresh, at 04:32." ───────────────────────
        bubble = SpeechBubble("Fresh, at 04:32.", anchor=maitre, side="right")
        self.play(FadeIn(bubble, run_time=0.3))
        self.wait(0.5)
        self.play(FadeOut(bubble, run_time=0.3))

        # ── handoff: maitre + tray + ticket + card move right ───────
        handoff_shift = np.array([4.2, 0, 0])
        self.play(
            maitre.animate.shift(handoff_shift),
            tray.animate.shift(handoff_shift),
            card.animate.shift(handoff_shift),
            ticket.animate.move_to(TICKET_END),
            run_time=1.5,
        )

        # ── camera hold ─────────────────────────────────────────────
        self.wait(3.6)

        self.remove(floor, maitre, tray, freezer, mist, card, ticket, caption)
