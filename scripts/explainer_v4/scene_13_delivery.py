"""Scene 13 — Delivery + click-through (~18 s, 2:42–3:00).

Maitre carries the plated answer (with the order ticket stapled to it)
back to the customer. Customer taps the [04:30] gold garnish; the
YouTube lecture on the table jumps from 04:32 to 04:30.

Render:
    manim -ql scripts/explainer_v4/scene_13_delivery.py Scene13Delivery
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
    FadeOut,
    Indicate,
    LEFT,
    Line,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Text,
    Transform,
    UP,
    VGroup,
    WHITE,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    OrderTicket,
    SpeechBubble,
    make_customer,
    make_maitre,
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


def _make_stamp(text: str, border_color: str) -> VGroup:
    label = Text(text, color=border_color, weight="BOLD").scale(0.27)
    bg = RoundedRectangle(
        width=label.width + 0.22, height=label.height + 0.16,
        corner_radius=0.05,
        stroke_color=border_color, stroke_width=2.0,
        fill_color="#FAFAFA", fill_opacity=0.95,
    )
    label.move_to(bg.get_center())
    return VGroup(bg, label)


def _make_plated_dish(center) -> tuple[VGroup, VGroup]:
    """Recreate Scene 12 end-state. Returns (dish_group, tag_0430)."""
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

    tag_0430 = _gold_tag("[04:30]", center + np.array([-1.30, -0.55, 0]))
    tag_0435 = _gold_tag("[04:35]", center + np.array([ 1.30, -0.55, 0]))
    tag_0502 = _gold_tag("[05:02]", center + np.array([ 0.0,  1.15, 0]))

    # stamps below plate
    stamp_y = center[1] - 1.40
    s1 = _make_stamp("Clarity 5/5", GREEN).move_to(np.array([center[0] - 1.6, stamp_y, 0]))
    s2 = _make_stamp("ECT 4/5",     AMBER).move_to(np.array([center[0] + 0.0, stamp_y, 0]))
    s3 = _make_stamp("UPT 5/5",     GREEN).move_to(np.array([center[0] + 1.6, stamp_y, 0]))

    dish = VGroup(plate, p1, p2, p3, p4, p4b, tag_0430, tag_0435, tag_0502, s1, s2, s3)
    return dish, tag_0430


def _make_youtube_screen(center, timecode: str) -> tuple[VGroup, Text, VGroup]:
    """A simplified YouTube player. Returns (group, time_label, frame_indicator)."""
    bezel = RoundedRectangle(
        width=2.4, height=1.5, corner_radius=0.06,
        stroke_color=WHITE, stroke_width=1.4,
        fill_color="#0A0C10", fill_opacity=1,
    )
    bezel.move_to(center)
    screen = Rectangle(
        width=2.2, height=1.2,
        stroke_color="#444", stroke_width=0.8,
        fill_color="#11161E", fill_opacity=1,
    )
    screen.move_to(center + np.array([0, 0.05, 0]))

    # tiny lecture slide inside: text lines representing a slide
    slide_title = Text("Gradient Descent", color="#A8C8FF", weight="BOLD").scale(0.14)
    slide_title.move_to(screen.get_center() + np.array([0, 0.25, 0]))
    slide_body = Text("The blue arrow shows\nthe negative direction", color="#888").scale(0.10)
    slide_body.move_to(screen.get_center() + np.array([0, -0.05, 0]))
    frame_indicator = VGroup(slide_title, slide_body)

    # progress bar
    bar_bg = Rectangle(width=2.0, height=0.05,
                       stroke_width=0, fill_color="#444", fill_opacity=1)
    bar_bg.move_to(center + np.array([0.0, -0.55, 0]))
    bar_fill = Rectangle(width=0.7, height=0.05,
                         stroke_width=0, fill_color=GOLD, fill_opacity=1)
    bar_fill.align_to(bar_bg, LEFT).align_to(bar_bg, DOWN)

    time_label = Text(timecode, color=WHITE).scale(0.24)
    time_label.move_to(center + np.array([0.85, -0.55, 0]))

    grp = VGroup(bezel, screen, frame_indicator, bar_bg, bar_fill, time_label)
    return grp, time_label, frame_indicator


class Scene13Delivery(BaseScene):
    def construct(self):
        # ── Counter + dish at kitchen position ────────────────────
        counter = _make_counter()
        self.add(counter)

        kitchen_dish_center = np.array([0.5, 0.30, 0])
        dish, tag_0430 = _make_plated_dish(kitchen_dish_center)
        self.add(dish)

        # ── Order ticket — recreate (q, t=04:32, video_id) ────────
        ticket = OrderTicket(
            question="What does the blue arrow at 4:32 mean?",
            timestamp="04:32",
            video_id="3OmfTIf-SOU",
        )
        ticket.move_to(np.array([5.5, 1.5, 0]))
        self.play(FadeIn(ticket, run_time=0.5))
        self.wait(0.5)

        # Plate "object" is the first child of dish — staple ticket to it
        plate_obj = dish[0]
        self.play(ticket.staple_to(plate_obj), run_time=1.1)

        # tiny staple icon
        staple = Line(
            ticket.get_corner(DOWN) + np.array([-0.06, 0.02, 0]),
            ticket.get_corner(DOWN) + np.array([ 0.06, 0.02, 0]),
            color="#888", stroke_width=2.5,
        )
        self.play(FadeIn(staple, run_time=0.2))

        # group ticket+staple with dish so they travel together
        full_dish = VGroup(dish, ticket, staple)

        # ── Maitre enters from screen-right, picks up the dish ────
        maitre = make_maitre()
        maitre.move_to(np.array([6.2, -1.05, 0]))
        self.play(FadeIn(maitre, run_time=0.4))
        self.play(maitre.animate.move_to(np.array([2.6, -1.05, 0])), run_time=1.2)
        self.wait(0.3)

        # ── Customer is already seated front-left at the table ────
        customer = make_customer()
        customer.move_to(np.array([-4.2, -2.55, 0]))
        self.add(customer)

        # ── YouTube screen on the table, frozen at 04:32 ──────────
        yt, yt_time, yt_indicator = _make_youtube_screen(
            np.array([2.7, -2.50, 0]), "04:32"
        )
        self.play(FadeIn(yt, run_time=0.6))
        self.wait(0.4)

        # ── Maitre walks dish to table (left of customer? no — between) ─
        table_dish_center = np.array([-1.6, -2.40, 0])

        # shrink + move dish to table
        self.play(
            full_dish.animate.scale(0.55).move_to(table_dish_center),
            maitre.animate.move_to(np.array([-0.2, -1.45, 0])),
            run_time=2.6,
        )
        self.wait(0.7)

        # tag_0430 has been transformed with full_dish — grab its current center
        tap_target = tag_0430.get_center()

        # ── Customer taps the [04:30] garnish — small ripple ─────
        self.play(Indicate(customer, scale_factor=1.10, run_time=0.4))
        ripple = Circle(radius=0.08, color=GOLD, stroke_width=2, fill_opacity=0)
        ripple.move_to(tap_target)
        self.add(ripple)
        self.play(
            ripple.animate.scale(4.0).set_stroke(opacity=0),
            run_time=1.0,
        )
        self.remove(ripple)
        self.play(Indicate(tag_0430, scale_factor=1.4, run_time=0.6))
        self.wait(0.4)

        # ── YouTube screen jumps 04:32 → 04:30; arrow indicator shifts ─
        new_time = Text("04:30", color=WHITE).scale(0.24)
        new_time.move_to(yt_time.get_center())
        self.play(Transform(yt_time, new_time), run_time=0.7)
        self.wait(0.3)

        # slide body text changes subtly to show a different frame
        new_body = Text("The negative gradient\npoints downhill", color="#888").scale(0.10)
        new_body.move_to(yt_indicator[1].get_center())
        self.play(Transform(yt_indicator[1], new_body), run_time=0.8)
        self.wait(0.4)

        # ── Customer bubble (≤ 5 words) ───────────────────────────
        bubble = SpeechBubble("That's the exact moment.", anchor=customer, side="right")
        bubble.show(self, duration=2.2)

        self.wait(1.4)
