"""Order-ticket Mobject — the running 'question card'."""

from __future__ import annotations

from manim import (
    DOWN,
    RoundedRectangle,
    Text,
    UP,
    VGroup,
    WHITE,
)


class OrderTicket(VGroup):
    """A small 1.6 × 1.0 card showing question / timestamp / video id."""

    def __init__(
        self,
        question: str,
        timestamp: str,
        video_id: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._question = question
        self._timestamp = timestamp
        self._video_id = video_id

        card = RoundedRectangle(
            width=4.2,
            height=1.8,
            corner_radius=0.10,
            stroke_color=WHITE,
            stroke_width=1.5,
            fill_color=WHITE,
            fill_opacity=0.92,
        )
        self._card = card

        # Split question into two lines if long
        if len(question) > 24:
            mid = len(question) // 2
            # find nearest space to mid
            sp = question.rfind(" ", 0, mid + 5)
            if sp == -1:
                sp = mid
            line1 = question[:sp]
            line2 = question[sp:].strip()
            q = Text(f"{line1}\n{line2}", color="#222").scale(0.18)
        else:
            q = Text(question, color="#222").scale(0.20)
        t = Text(f"t = {timestamp}", color="#444").scale(0.20)
        v = Text(video_id[:12], color="#666").scale(0.18)
        q.move_to(card.get_center() + UP * 0.30)
        t.next_to(q, DOWN, buff=0.12)
        v.next_to(t, DOWN, buff=0.06)

        self._q, self._t, self._v = q, t, v
        self.add(card, q, t, v)

    def update_question(self, new_text: str) -> "OrderTicket":
        new_q = Text(new_text[:40], color="#222").scale(0.24)
        new_q.move_to(self._q.get_center())
        self.remove(self._q)
        self._q = new_q
        self.add(new_q)
        self._question = new_text
        return self

    def staple_to(self, mobject):
        """Animation helper: move ticket to top-right of `mobject`."""
        target = mobject.get_corner(UP) + (0.6 * UP)
        return self.animate.scale(0.7).move_to(target)
