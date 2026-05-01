"""Lightweight pi-creature stand-ins for restaurant characters."""

from __future__ import annotations

import numpy as np
from manim import (
    Arc,
    BLACK,
    Circle,
    DOWN,
    Dot,
    PI,
    Text,
    UP,
    VGroup,
)

from .palette import (
    CRITIC,
    CUSTOMER,
    INDIE,
    LENS,
    MAITRE,
    QUILL,
    VEE,
)


class PiChef(VGroup):
    """Pastel circle-body stand-in for a Manim PiCreature."""

    def __init__(self, name: str, color: str, label_text: str, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.color = color

        body = Circle(radius=0.65, color=color, fill_opacity=1, stroke_width=0)
        eye_l = Dot(point=np.array([-0.22, 0.14, 0]), radius=0.07, color=BLACK)
        eye_r = Dot(point=np.array([ 0.22, 0.14, 0]), radius=0.07, color=BLACK)
        mouth = Arc(
            radius=0.14,
            start_angle=PI + 0.4,
            angle=PI - 0.8,
            color=BLACK,
            stroke_width=2.5,
        ).move_to(np.array([0, -0.14, 0]))

        self._body = body
        self._eye_l = eye_l
        self._eye_r = eye_r
        self._mouth = mouth

        label = Text(label_text, color=color).scale(0.34)
        label.next_to(body, DOWN, buff=0.10)
        self._label = label

        self._prop: VGroup | None = None
        self.add(body, eye_l, eye_r, mouth, label)

    # ── animation helpers ─────────────────────────────────────────
    def walk_to(self, point, run_time: float = 1.0):
        """Return an animation that walks the chef to `point`."""
        return self.animate(run_time=run_time).move_to(point + np.array([0, 0.45, 0]))

    def hold_prop(self, mobject) -> VGroup:
        """Attach a small mobject above-right of the body."""
        mobject.scale(0.6)
        mobject.next_to(self._body, UP, buff=0.05)
        if self._prop is not None:
            self.remove(self._prop)
        self._prop = mobject
        self.add(mobject)
        return self

    def set_expression(self, mood: str = "neutral") -> "PiChef":
        """Swap the mouth arc for a few canned moods."""
        if mood == "happy":
            new = Arc(radius=0.17, start_angle=PI + 0.2, angle=PI - 0.4,
                      color=BLACK, stroke_width=2.5)
        elif mood == "thinking":
            new = Arc(radius=0.09, start_angle=0, angle=PI,
                      color=BLACK, stroke_width=2.5)
        else:  # neutral
            new = Arc(radius=0.14, start_angle=PI + 0.4, angle=PI - 0.8,
                      color=BLACK, stroke_width=2.5)
        new.move_to(self._mouth.get_center())
        self.remove(self._mouth)
        self._mouth = new
        self.add(new)
        return self


# ── factory functions (color + label baked in) ───────────────────
def make_maitre()   -> PiChef: return PiChef("maitre",   MAITRE,   "Router")
def make_quill()    -> PiChef: return PiChef("quill",    QUILL,    "Scribe")
def make_lens()     -> PiChef: return PiChef("lens",     LENS,     "Scan")
def make_indie()    -> PiChef: return PiChef("indie",    INDIE,    "Indexer")
def make_vee()      -> PiChef: return PiChef("vee",      VEE,      "VLM")
def make_critic()   -> PiChef: return PiChef("critic",   CRITIC,   "Judge")
def make_customer() -> PiChef: return PiChef("customer", CUSTOMER, "You")
