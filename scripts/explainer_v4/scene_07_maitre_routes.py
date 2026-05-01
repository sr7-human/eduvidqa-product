"""Scene 7 — Maitre routes the ticket (~10 s, 1:08–1:18).

Maitre snatches the ticket off the dining table, hustles past the
pantry into the library, dropping it at Indie's reading desk.
Faint dotted route line traces behind. `POST /api/ask` tag flashes
top-right. Lower-third label `Maitre — FastAPI · backend/app.py`.

Ticket continuity:
    TICKET_START = np.array([0.0, -2.55, 0])      # = end of Scene 6
    TICKET_END   = np.array([-0.5, -2.30, 0])     # at library reading desk

Render:
    manim -ql scripts/explainer_v4/scene_07_maitre_routes.py Scene07MaitreRoutes
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DashedLine,
    DOWN,
    FadeIn,
    FadeOut,
    LEFT,
    RIGHT,
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


TICKET_START = np.array([0.0, -2.55, 0])    # = end of Scene 6
TICKET_END = np.array([-0.5, -2.30, 0])     # library reading desk


class Scene07MaitreRoutes(BaseScene):
    def construct(self):
        # ── floorplan ───────────────────────────────────────────────
        floor = RestaurantFloorplan()
        self.add(floor)

        # ── ticket already at end-of-scene-6 position ───────────────
        ticket = OrderTicket(
            question="What does the blue arrow at 4:32 mean?",
            timestamp="04:32",
            video_id="3OmfTIf-SOU",
        )
        ticket.scale(0.7).move_to(TICKET_START)
        self.add(ticket)
        self.wait(0.4)

        # ── maitre enters from screen-right ─────────────────────────
        maitre = make_maitre()
        maitre.move_to(np.array([4.0, -2.05, 0]))
        self.add(maitre)

        # lower-third label runs in parallel with maitre's first walk
        self.play(
            maitre.animate.move_to(TICKET_START + np.array([0.6, 0.45, 0])),
            lower_third_label(maitre, "Router — FastAPI · backend/app.py"),
            run_time=2.0,
        )

        # ── PICKUP: ticket lifts off table and snaps to maitre's hand ──
        ticket_carry_offset = np.array([-0.35, 0.55, 0])
        # first lift up a bit (visible "grabbing" beat)
        self.play(ticket.animate.shift(UP * 0.35), run_time=0.4)
        self.play(
            ticket.animate.move_to(maitre.get_center() + ticket_carry_offset),
            run_time=0.5,
        )
        # brief hold so viewer sees ticket is now in the router's hand
        self.wait(0.6)

        # ── speech bubble: "Order in!" ──────────────────────────────
        bubble = SpeechBubble("Order in!", anchor=maitre, side="right")
        self.play(FadeIn(bubble, run_time=0.3))

        # ── POST /api/ask tag (top-right) ───────────────────────────
        post_tag = Text("POST /api/ask", color="#888").scale(0.42)
        post_tag.move_to(np.array([3.0, 2.5, 0]))
        self.play(FadeIn(post_tag, run_time=0.3))

        self.wait(0.5)
        self.play(FadeOut(bubble, run_time=0.3))

        # ── CARRY: maitre walks the ticket across the floor ────────
        # slow + linear so the route reads clearly
        self.play(
            maitre.animate.move_to(TICKET_END + np.array([0.6, 0.45, 0])),
            ticket.animate.move_to(TICKET_END + np.array([0.6, 0.45, 0]) + ticket_carry_offset),
            run_time=3.0,
            rate_func=lambda t: t,
        )

        # ── DROP: ticket lands on the indexer's desk with a held beat ──
        self.play(
            ticket.animate.move_to(TICKET_END),
            run_time=0.7,
        )
        # "delivered" indicator: small bubble from maitre
        delivered = SpeechBubble("For Indexer.", anchor=maitre, side="left")
        self.play(FadeIn(delivered, run_time=0.3))
        self.wait(1.2)
        self.play(FadeOut(delivered, run_time=0.3))

        # POST tag fades
        self.play(FadeOut(post_tag, run_time=0.3))

        self.wait(0.8)

        self.remove(floor, maitre, ticket)
