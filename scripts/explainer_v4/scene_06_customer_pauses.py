"""Scene 6 — The customer pauses (~13 s, 0:55–1:08).

Customer at table; YouTube lecture pauses at 04:32; customer types
"What does the blue arrow at 4:32 mean?" into a notepad; printer prints
the OrderTicket onto the table.

Ticket end-position (handed to Scene 7):
    TICKET_END = np.array([0.0, -2.55, 0])    # on dining table, slightly forward of customer

Render:
    manim -ql scripts/explainer_v4/scene_06_customer_pauses.py Scene06CustomerPauses
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    AddTextLetterByLetter,
    Circle,
    DOWN,
    Dot,
    FadeIn,
    FadeOut,
    LEFT,
    Line,
    Polygon,
    RIGHT,
    Rectangle,
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
    make_customer,
)


# Ticket continuity: end-of-scene-6 position == start-of-scene-7
TICKET_END = np.array([0.0, -2.55, 0])


def _make_lecture_screen() -> VGroup:
    """16:9 lecture rectangle with a tiny neural-net diagram + timecode."""
    screen = Rectangle(
        width=4.5, height=2.55,
        stroke_color=WHITE, stroke_width=1.5,
        fill_color="#1B1F27", fill_opacity=1,
    )
    # 3-column neural net (3-4-3 dots)
    cols = [
        [(-1.4, 0.6), (-1.4, 0.0), (-1.4, -0.6)],
        [(0.0, 0.9), (0.0, 0.3), (0.0, -0.3), (0.0, -0.9)],
        [(1.4, 0.6), (1.4, 0.0), (1.4, -0.6)],
    ]
    nodes = []
    for col in cols:
        for x, y in col:
            d = Dot(point=np.array([x, y, 0]), radius=0.08, color="#A8C8FF")
            nodes.append(d)
    edges = []
    for x1, y1 in [(p) for p in cols[0]]:
        for x2, y2 in [(p) for p in cols[1]]:
            edges.append(Line(
                np.array([x1, y1, 0]), np.array([x2, y2, 0]),
                stroke_color="#3A5A8C", stroke_width=1.0,
            ))
    for x1, y1 in [(p) for p in cols[1]]:
        for x2, y2 in [(p) for p in cols[2]]:
            edges.append(Line(
                np.array([x1, y1, 0]), np.array([x2, y2, 0]),
                stroke_color="#3A5A8C", stroke_width=1.0,
            ))
    nn = VGroup(*edges, *nodes)

    timecode = Text("04:32 / 18:47", color="#DDD").scale(0.3)
    timecode.move_to(screen.get_corner(DOWN + RIGHT) + np.array([-0.65, 0.18, 0]))

    grp = VGroup(screen, nn, timecode)
    return grp


def _make_play_button() -> Polygon:
    return Polygon(
        np.array([-0.10, 0.15, 0]),
        np.array([-0.10, -0.15, 0]),
        np.array([0.18, 0.0, 0]),
        stroke_color=WHITE, stroke_width=1.0,
        fill_color=WHITE, fill_opacity=0.9,
    )


def _make_pause_icon() -> VGroup:
    bar1 = Rectangle(
        width=0.07, height=0.30,
        stroke_width=0, fill_color=WHITE, fill_opacity=0.9,
    ).move_to(np.array([-0.08, 0, 0]))
    bar2 = Rectangle(
        width=0.07, height=0.30,
        stroke_width=0, fill_color=WHITE, fill_opacity=0.9,
    ).move_to(np.array([0.08, 0, 0]))
    return VGroup(bar1, bar2)


def _make_notepad() -> VGroup:
    pad = RoundedRectangle(
        width=3.2, height=0.9, corner_radius=0.06,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#FFF8E0", fill_opacity=0.95,
    )
    return VGroup(pad)


def _make_printer() -> VGroup:
    body = RoundedRectangle(
        width=1.0, height=0.5, corner_radius=0.05,
        stroke_color=WHITE, stroke_width=1.2,
        fill_color="#3A3F4B", fill_opacity=1,
    )
    slot = Rectangle(
        width=0.7, height=0.05,
        stroke_width=0, fill_color="#111", fill_opacity=1,
    ).next_to(body, UP, buff=-0.08)
    label = Text("printer", color="#DDD").scale(0.2).move_to(body.get_center())
    return VGroup(body, slot, label)


class Scene06CustomerPauses(BaseScene):
    def construct(self):
        # ── floorplan + customer ────────────────────────────────────
        floor = RestaurantFloorplan()
        self.play(FadeIn(floor, run_time=0.4))

        customer = make_customer()
        customer.move_to(np.array([-1.4, -2.3, 0]))
        self.play(FadeIn(customer, run_time=0.4))

        # ── lecture screen above the table ──────────────────────────
        lecture = _make_lecture_screen()
        lecture.move_to(np.array([0.0, 0.6, 0]))
        self.play(FadeIn(lecture, run_time=0.6))

        # play button overlay
        play_btn = _make_play_button()
        play_btn.move_to(lecture.get_center() + np.array([0, -0.05, 0]))
        self.play(FadeIn(play_btn, run_time=0.3))

        # ── pause beat: play → pause + timecode flash ───────────────
        pause_icon = _make_pause_icon().move_to(play_btn.get_center())
        self.play(FadeOut(play_btn, run_time=0.15), FadeIn(pause_icon, run_time=0.15))

        # timecode flash (the timecode is the last child of `lecture`)
        timecode = lecture[-1]
        self.play(timecode.animate.set_color("#FF6B9D"), run_time=0.2)
        self.play(timecode.animate.set_color("#DDD"), run_time=0.2)

        # ── notepad with question typed letter-by-letter ────────────
        notepad = _make_notepad()
        notepad.move_to(np.array([2.6, -2.3, 0]))
        self.play(FadeIn(notepad, run_time=0.3))

        question = Text(
            "What does the blue arrow at 4:32 mean?",
            color="#222",
        ).scale(0.33)
        question.move_to(notepad.get_center())
        self.play(AddTextLetterByLetter(question, run_time=2.5))

        # ── printer prints the order ticket ─────────────────────────
        printer = _make_printer()
        printer.move_to(np.array([1.4, -2.5, 0]))
        self.play(FadeIn(printer, run_time=0.3))

        # tiny chk-chk-chk: jiggle printer twice
        self.play(printer.animate.shift(UP * 0.05), run_time=0.10)
        self.play(printer.animate.shift(DOWN * 0.05), run_time=0.10)
        self.play(printer.animate.shift(UP * 0.05), run_time=0.10)
        self.play(printer.animate.shift(DOWN * 0.05), run_time=0.10)

        ticket = OrderTicket(
            question="What does the blue arrow at 4:32 mean?",
            timestamp="04:32",
            video_id="3OmfTIf-SOU",
        )
        ticket.scale(0.7)
        ticket.move_to(printer.get_top() + np.array([0, 0.05, 0]))
        ticket.set_opacity(0.0)
        self.add(ticket)
        self.play(ticket.animate.set_opacity(1.0).shift(UP * 0.5), run_time=0.7)

        # slide ticket forward to its end-of-scene position on the table
        self.play(ticket.animate.move_to(TICKET_END), run_time=0.6)

        # ── camera holds ────────────────────────────────────────────
        self.wait(5.6)

        self.remove(floor, customer, lecture, pause_icon, notepad, question, printer, ticket)
