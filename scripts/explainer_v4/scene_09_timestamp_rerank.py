"""Scene 9 — Timestamp re-rank (~12 s, 1:40–1:52).

Indie sets the tray on a turntable; spin reshuffles items so that
those with timestamps closest to 04:32 rise to the top, far ones
sink. A "distance from 04:32" bar appears alongside.

Ticket continuity:
    TICKET_START = np.array([2.4, 0.0, 0])    # beside tray (locally placed)
    TICKET_END   = np.array([2.4, -1.2, 0])   # next to tray, ready for Scene 10

Render:
    manim -ql scripts/explainer_v4/scene_09_timestamp_rerank.py Scene09TimestampRerank
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    Circle,
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    Line,
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
    make_indie,
)


TICKET_START = np.array([2.4, 0.0, 0])
TICKET_END = np.array([2.4, -1.2, 0])

TARGET_SECONDS = 4 * 60 + 32   # 04:32


def _ts_to_seconds(ts: str) -> int:
    m, s = ts.split(":")
    return int(m) * 60 + int(s)


def _make_scroll(label: str) -> VGroup:
    body = RoundedRectangle(
        width=0.55, height=0.22, corner_radius=0.05,
        stroke_color=WHITE, stroke_width=1.0,
        fill_color="#E8DCC2", fill_opacity=0.95,
    )
    tag = Text(f"[{label}]", color="#FFD27F", weight="BOLD").scale(0.2)
    tag.next_to(body, RIGHT, buff=0.10)
    return VGroup(body, tag)


def _make_photo(label: str) -> VGroup:
    body = Rectangle(
        width=0.40, height=0.28,
        stroke_color=WHITE, stroke_width=1.0,
        fill_color="#A8C8FF", fill_opacity=0.95,
    )
    tag = Text(f"[{label}]", color="#FFD27F", weight="BOLD").scale(0.2)
    tag.next_to(body, RIGHT, buff=0.10)
    return VGroup(body, tag)


class Scene09TimestampRerank(BaseScene):
    def construct(self):
        # ── floorplan ───────────────────────────────────────────────
        floor = RestaurantFloorplan()
        self.add(floor)
        self.wait(0.4)

        # ── Indie at the library reading area ───────────────────────
        indie = make_indie()
        indie.move_to(np.array([-2.5, 0.5, 0]))
        self.add(indie)

        # ── tray contents (kind, timestamp) ─────────────────────────
        items_spec = [
            ("scroll", "04:30"),
            ("scroll", "04:35"),
            ("scroll", "05:02"),
            ("scroll", "03:50"),
            ("scroll", "07:10"),
            ("photo",  "04:32"),
            ("photo",  "08:05"),
            ("photo",  "16:22"),
        ]

        # build mobjects
        items: list[tuple[VGroup, int]] = []   # (mob, distance_from_target)
        for kind, ts in items_spec:
            mob = _make_scroll(ts) if kind == "scroll" else _make_photo(ts)
            d = abs(_ts_to_seconds(ts) - TARGET_SECONDS)
            items.append((mob, d))

        # initial tray layout: original (un-sorted) vertical column
        tray_x = 0.5
        top_y = 1.8
        spacing = 0.42
        for i, (mob, _d) in enumerate(items):
            mob.move_to(np.array([tray_x, top_y - i * spacing, 0]))

        # turntable circle under the tray
        turntable = Circle(
            radius=1.8,
            color="#4A5060",
            stroke_width=1.5,
            fill_color="#1B1F27",
            fill_opacity=0.6,
        )
        turntable.move_to(np.array([tray_x, top_y - (len(items) - 1) * spacing / 2, 0]))

        # tray rectangle (visual frame)
        tray_frame = Rectangle(
            width=1.6, height=len(items) * spacing + 0.2,
            stroke_color=WHITE, stroke_width=1.0,
            fill_opacity=0,
        )
        tray_frame.move_to(turntable.get_center())

        items_group = VGroup(*[m for m, _ in items])

        self.play(
            FadeIn(turntable, run_time=0.4),
            FadeIn(tray_frame, run_time=0.4),
        )
        self.play(FadeIn(items_group, run_time=0.4))

        # ── reference ticket beside the tray ────────────────────────
        ticket = OrderTicket(
            question="What does the blue arrow at 4:32 mean?",
            timestamp="04:32",
            video_id="3OmfTIf-SOU",
        )
        ticket.scale(0.7).move_to(TICKET_START)
        self.play(FadeIn(ticket, run_time=0.4))

        # ── Indie speech bubble (≤ 5 words) ─────────────────────────
        bubble = SpeechBubble("Closer in time, top.", anchor=indie, side="right")
        self.play(FadeIn(bubble, run_time=0.3))

        # ── distance bar on the left ────────────────────────────────
        bar_x = -3.0
        bar_top = top_y
        bar_bot = top_y - (len(items) - 1) * spacing
        axis = Line(
            np.array([bar_x, bar_top, 0]), np.array([bar_x, bar_bot, 0]),
            stroke_color="#888", stroke_width=2.0,
        )
        bar_label_top = Text("close to 04:32", color="#AAA").scale(0.24)
        bar_label_top.next_to(np.array([bar_x, bar_top, 0]), LEFT, buff=0.10)
        bar_label_bot = Text("far", color="#AAA").scale(0.24)
        bar_label_bot.next_to(np.array([bar_x, bar_bot, 0]), LEFT, buff=0.10)
        self.play(
            FadeIn(axis, run_time=0.3),
            FadeIn(bar_label_top, run_time=0.3),
            FadeIn(bar_label_bot, run_time=0.3),
        )

        # ── spin the turntable & reorder items ──────────────────────
        # compute new positions sorted by distance ascending
        sorted_items = sorted(items, key=lambda p: p[1])
        new_positions = {}
        for i, (mob, _d) in enumerate(sorted_items):
            new_positions[id(mob)] = np.array([tray_x, top_y - i * spacing, 0])

        # marker dots on distance axis at new ordering
        markers = VGroup()
        for i in range(len(items)):
            y = top_y - i * spacing
            markers.add(Circle(radius=0.05, color="#FFC58A",
                               fill_color="#FFC58A", fill_opacity=1, stroke_width=0)
                        .move_to(np.array([bar_x, y, 0])))

        self.play(
            Rotate(turntable, angle=PI, run_time=2.0),
            FadeIn(markers, run_time=2.0),
        )

        # reorder animation
        self.play(
            *[mob.animate.move_to(new_positions[id(mob)]) for mob, _ in items],
            run_time=1.0,
        )

        # bubble out, ticket settle to end pos
        self.play(FadeOut(bubble, run_time=0.4))
        self.play(ticket.animate.move_to(TICKET_END), run_time=0.5)

        # ── camera holds ────────────────────────────────────────────
        self.wait(5.8)

        self.remove(floor, indie, turntable, tray_frame, items_group, axis, bar_label_top, bar_label_bot, markers, ticket)
