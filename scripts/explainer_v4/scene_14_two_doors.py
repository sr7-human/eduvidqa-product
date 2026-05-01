"""Scene 14 — Split-screen: ChatGPT vs EduVidQA (~25 s).

Clean side-by-side comparison. Same question asked to both.
Left = ChatGPT gives generic answer, shrugs.
Right = EduVidQA gives grounded answer with [mm:ss] citations.
Tagline at end.

Render:
    manim -qh scripts/explainer_v4/scene_14_two_doors.py Scene14TwoDoors
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    Create,
    DOWN,
    DashedLine,
    FadeIn,
    FadeOut,
    LEFT,
    Line,
    RIGHT,
    RoundedRectangle,
    Text,
    UP,
    Underline,
    VGroup,
    WHITE,
    Wiggle,
    Write,
)

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from explainer_v4_lib import (  # noqa: E402
    BaseScene,
    SpeechBubble,
    make_customer,
)

GOLD = "#FFD66B"
FAIL = "#EF5350"
OK = "#81C784"


class Scene14TwoDoors(BaseScene):
    def construct(self):
        self.wait(0.3)

        # ── divider line down the center ──────────────────────────
        divider = DashedLine(
            UP * 3.2, DOWN * 2.0,
            color="#4A5060", stroke_width=2, dash_length=0.15,
        )

        # ── LEFT SIDE: ChatGPT ────────────────────────────────────
        left_title = Text("Generic LLM", color="#9AA0A6", weight="BOLD").scale(0.7)
        left_title.move_to(np.array([-2.8, 2.5, 0]))

        # question
        left_q = Text('"What does the blue arrow at 4:32 mean?"',
                      color=WHITE).scale(0.32)
        left_q.move_to(np.array([-2.8, 1.6, 0]))

        # generic answer box
        left_box = RoundedRectangle(
            width=4.5, height=1.8, corner_radius=0.12,
            stroke_color="#4A5060", stroke_width=1.5,
            fill_color="#1A1D22", fill_opacity=1,
        )
        left_box.move_to(np.array([-2.8, 0.0, 0]))

        left_a1 = Text("An arrow in a gradient diagram typically",
                        color="#9AA0A6").scale(0.3)
        left_a2 = Text("shows the direction of steepest ascent.",
                        color="#9AA0A6").scale(0.3)
        left_a3 = Text("The blue color may indicate...",
                        color="#9AA0A6").scale(0.3)
        left_ans = VGroup(left_a1, left_a2, left_a3).arrange(DOWN, buff=0.12)
        left_ans.move_to(left_box.get_center())

        # verdict
        left_verdict = Text("Generic. No lecture context.",
                            color=FAIL, weight="BOLD").scale(0.3)
        left_verdict.next_to(left_box, DOWN, buff=0.3)

        # bot character
        bot = make_customer()
        bot._body.set_color("#7A7F8A")
        bot._label.set_color("#7A7F8A")
        bot._label.become(Text("bot", color="#7A7F8A").scale(0.34).move_to(bot._label))
        bot.move_to(np.array([-2.8, -2.5, 0]))

        # ── RIGHT SIDE: EduVidQA ──────────────────────────────────
        right_title = Text("EduVidQA", color=GOLD, weight="BOLD").scale(0.7)
        right_title.move_to(np.array([2.8, 2.5, 0]))
        right_ul = Underline(right_title, color=GOLD, buff=0.06)

        # same question
        right_q = Text('"What does the blue arrow at 4:32 mean?"',
                       color=WHITE).scale(0.32)
        right_q.move_to(np.array([2.8, 1.6, 0]))

        # grounded answer box
        right_box = RoundedRectangle(
            width=4.5, height=1.8, corner_radius=0.12,
            stroke_color=GOLD, stroke_width=2,
            fill_color="#1A2320", fill_opacity=1,
        )
        right_box.move_to(np.array([2.8, 0.0, 0]))

        right_a1 = Text("At [04:32] the professor draws the negative",
                         color=WHITE).scale(0.3)
        right_a2 = Text("gradient direction. Compare with [02:15]",
                         color=WHITE).scale(0.3)
        right_a3 = Text("where she drew the opposite sign.",
                         color=WHITE).scale(0.3)
        right_ans = VGroup(right_a1, right_a2, right_a3).arrange(DOWN, buff=0.12)
        right_ans.move_to(right_box.get_center())

        # gold citation tags
        tags = VGroup(
            Text("[04:32]", color=GOLD).scale(0.32),
            Text("[02:15]", color=GOLD).scale(0.32),
            Text("[05:02]", color=GOLD).scale(0.32),
        ).arrange(RIGHT, buff=0.4)
        tags.next_to(right_box, DOWN, buff=0.2)

        # verdict
        right_verdict = Text("Grounded. Verifiable. Click to jump.",
                             color=OK, weight="BOLD").scale(0.3)
        right_verdict.next_to(tags, DOWN, buff=0.2)

        # student character
        student = make_customer()
        student.move_to(np.array([2.8, -2.5, 0]))

        # ── ANIMATION SEQUENCE ────────────────────────────────────

        # 1. Show both titles + divider
        self.play(
            FadeIn(left_title, run_time=0.5),
            FadeIn(right_title, run_time=0.5),
            Write(right_ul, run_time=0.5),
            Create(divider, run_time=0.6),
        )
        self.wait(0.3)

        # 2. Show same question on both sides
        self.play(
            FadeIn(left_q, shift=DOWN * 0.1, run_time=0.6),
            FadeIn(right_q, shift=DOWN * 0.1, run_time=0.6),
        )
        self.wait(0.5)

        # 3. Left side: generic answer
        self.play(FadeIn(left_box, run_time=0.4))
        self.play(FadeIn(left_ans, run_time=0.8))
        self.play(FadeIn(left_verdict, shift=UP * 0.1, run_time=0.6))
        self.play(FadeIn(bot, run_time=0.4))
        self.wait(0.8)

        # Bot shrugs
        bubble = SpeechBubble("...what arrow?", anchor=bot, side="right")
        bubble.show(self, duration=1.5)

        # 4. Right side: grounded answer
        self.play(FadeIn(right_box, run_time=0.4))
        self.play(FadeIn(right_ans, run_time=0.8))
        self.play(FadeIn(tags, run_time=0.5))
        self.play(FadeIn(right_verdict, shift=UP * 0.1, run_time=0.6))
        self.play(FadeIn(student, run_time=0.4))
        self.wait(1.0)

        # 5. Dim left side
        self.play(
            left_title.animate.set_opacity(0.3),
            left_q.animate.set_opacity(0.3),
            left_box.animate.set_opacity(0.3),
            left_ans.animate.set_opacity(0.3),
            left_verdict.animate.set_opacity(0.3),
            bot.animate.set_opacity(0.3),
            run_time=0.8,
        )
        self.wait(1.5)

        # 6. Tagline
        tagline_pre = Text("Every answer is traceable to a ",
                           color=WHITE).scale(0.5)
        tagline_moment = Text("moment", color=GOLD, weight="BOLD").scale(0.5)
        tagline_post = Text(" in the lecture.", color=WHITE).scale(0.5)
        tagline = VGroup(tagline_pre, tagline_moment, tagline_post).arrange(RIGHT, buff=0.05)
        tagline.move_to(np.array([0, -2.8, 0]))
        moment_underline = Underline(tagline_moment, color=GOLD, buff=0.05)

        self.play(FadeIn(tagline, run_time=0.8))
        self.play(Write(moment_underline, run_time=0.4))
        self.wait(3.0)

        # cleanup
        self.play(
            FadeOut(VGroup(
                left_title, left_q, left_box, left_ans, left_verdict, bot,
                right_title, right_ul, right_q, right_box, right_ans, tags,
                right_verdict, student, divider,
                tagline, moment_underline,
            ), run_time=0.5),
        )
