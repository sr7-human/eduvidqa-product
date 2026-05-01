"""EduVidQA USP-focused explainer — Manim Community 0.20.1.

Run:
    manim -ql scripts/explainer_v2.py EduVidQAExplainer
    manim -qm scripts/explainer_v2.py EduVidQAExplainer   # 720p30

5 scenes, ~100s target. USP = timestamp-grounded answers, not generic Q&A.
Split-screen ChatGPT vs EduVidQA as the killer moment.
"""

from __future__ import annotations

from manim import (
    DOWN,
    GREY_B,
    GREY_D,
    LEFT,
    RIGHT,
    UP,
    WHITE,
    Arrow,
    Create,
    Cross,
    DashedVMobject,
    Dot,
    DrawBorderThenFill,
    FadeIn,
    FadeOut,
    GrowArrow,
    GrowFromCenter,
    Indicate,
    Line,
    Rectangle,
    RoundedRectangle,
    Scene,
    SurroundingRectangle,
    Text,
    Transform,
    VGroup,
    Write,
    rate_functions,
)

# ── palette ──
BG      = "#0E1116"
ACCENT  = "#4FC3F7"   # cyan
GOLD    = "#FFD54F"   # amber / highlight
OK      = "#81C784"   # green
FAIL    = "#EF5350"   # red
MUTED   = "#9AA0A6"   # grey caption


def _box(w: float, h: float, color: str = GREY_D, fill: str = "#1A1D22") -> RoundedRectangle:
    return RoundedRectangle(
        corner_radius=0.15, width=w, height=h,
        stroke_color=color, stroke_width=2, fill_color=fill, fill_opacity=1,
    )


def _node(title: str, sub: str, color: str = ACCENT, w: float = 2.4, h: float = 0.95) -> VGroup:
    box = RoundedRectangle(
        corner_radius=0.15, width=w, height=h,
        stroke_color=color, stroke_width=2.5, fill_color=BG, fill_opacity=0.92,
    )
    t = Text(title, font="Helvetica", weight="BOLD", color=WHITE).scale(0.3)
    s = Text(sub, font="Helvetica", color=MUTED).scale(0.22)
    t.next_to(box.get_center(), UP, buff=0.04)
    s.next_to(t, DOWN, buff=0.06)
    return VGroup(box, t, s)


def _arrow_lr(a: VGroup, b: VGroup, color: str = GREY_B) -> Arrow:
    return Arrow(a.get_right(), b.get_left(), buff=0.1, stroke_width=3,
                 max_tip_length_to_length_ratio=0.12, color=color)


def _arrow_rl(a: VGroup, b: VGroup, color: str = GREY_B) -> Arrow:
    return Arrow(a.get_left(), b.get_right(), buff=0.1, stroke_width=3,
                 max_tip_length_to_length_ratio=0.12, color=color)


class EduVidQAExplainer(Scene):
    def construct(self) -> None:
        self.camera.background_color = BG

        self._scene_title()       # ~10 s
        self._scene_problem()     # ~22 s  (lecture-specific question + scrub)
        self._scene_pipeline()    # ~30 s  (how it works, brief)
        self._scene_splitscreen() # ~28 s  (ChatGPT vs EduVidQA — the USP)
        self._scene_cta()         # ~12 s

    # ═══════════════════════════════════════════════════════════════════
    # 1  TITLE
    # ═══════════════════════════════════════════════════════════════════
    def _scene_title(self) -> None:
        dot = Dot(color=ACCENT, radius=0.18).shift(LEFT * 2.2)
        title = Text("EduVidQA", font="Helvetica", weight="BOLD",
                      color=WHITE).scale(1.15).next_to(dot, RIGHT, buff=0.25)
        tagline = Text(
            "Ask a lecture video — get answers grounded in the exact moment.",
            font="Helvetica", color=MUTED,
        ).scale(0.36).next_to(VGroup(dot, title), DOWN, buff=0.35)

        self.play(GrowFromCenter(dot), run_time=0.5)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=0.8)
        self.play(FadeIn(tagline, shift=UP * 0.15), run_time=0.8)
        self.play(Indicate(dot, color=GOLD, scale_factor=1.5), run_time=0.7)
        self.wait(5.5)
        self.play(FadeOut(VGroup(dot, title, tagline)), run_time=0.7)

    # ═══════════════════════════════════════════════════════════════════
    # 2  THE PROBLEM — a question only THIS lecture can answer
    # ═══════════════════════════════════════════════════════════════════
    def _scene_problem(self) -> None:
        heading = Text("2 AM. No TA. A doubt at 32:40.",
                       font="Helvetica", weight="BOLD", color=WHITE).scale(0.55)
        heading.to_edge(UP, buff=0.6)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # ── mock player ──
        player = _box(6.0, 3.0)
        player.shift(UP * 0.3)
        time_lbl = Text("32:40 / 48:12", font="Helvetica", color=MUTED).scale(0.28)
        time_lbl.move_to(player.get_top() + DOWN * 0.22)

        # fake slide: a chain-rule equation on a whiteboard
        board = Rectangle(width=4.8, height=1.6, stroke_width=0,
                          fill_color="#2B2D30", fill_opacity=1)
        board.move_to(player.get_center() + UP * 0.15)
        eq_line1 = Text("dL/dw  =  dL/dy · dy/dw", font="Courier",
                        color=WHITE).scale(0.34).move_to(board.get_center() + UP * 0.2)
        eq_line2 = Text('"the gradient flows backward"', font="Helvetica",
                        color=GOLD).scale(0.26).next_to(eq_line1, DOWN, buff=0.15)

        # progress bar
        bar_bg = Line(player.get_left() + RIGHT * 0.3 + DOWN * 1.3,
                      player.get_right() + LEFT * 0.3 + DOWN * 1.3,
                      color=GREY_D, stroke_width=4)
        bar_fg = Line(bar_bg.get_start(),
                      bar_bg.get_start() + RIGHT * 3.6,
                      color=FAIL, stroke_width=4)
        head = Dot(bar_fg.get_end(), color=FAIL, radius=0.07)

        self.play(DrawBorderThenFill(player), FadeIn(time_lbl), run_time=0.9)
        self.play(FadeIn(board), FadeIn(eq_line1), FadeIn(eq_line2), run_time=0.8)
        self.play(Create(bar_bg), Create(bar_fg), FadeIn(head), run_time=0.6)

        # ── student question — lecture-specific, NOT textbook ──
        q_bubble = _box(5.6, 0.85, color=GOLD)
        q_txt = Text('"Which example did the professor use to explain',
                     font="Helvetica", color=WHITE).scale(0.28)
        q_txt2 = Text('the chain rule here?"',
                      font="Helvetica", color=WHITE).scale(0.28)
        q_content = VGroup(q_txt, q_txt2).arrange(DOWN, buff=0.06)
        q_content.move_to(q_bubble.get_center())
        q_grp = VGroup(q_bubble, q_content).next_to(player, DOWN, buff=0.3)

        self.play(FadeIn(q_grp, shift=UP * 0.2), run_time=0.8)
        self.wait(1.2)

        # ── scrubbing frustration ──
        for x in [2.0, 4.5, 1.5, 3.8]:
            end = bar_bg.get_start() + RIGHT * x
            self.play(head.animate.move_to(end),
                      bar_fg.animate.put_start_and_end_on(bar_bg.get_start(), end),
                      run_time=0.4, rate_func=rate_functions.ease_in_out_sine)

        scrub = Text("7 minutes scrubbing. Doubt still unclear.",
                     font="Helvetica", color=MUTED).scale(0.36)
        scrub.next_to(q_grp, DOWN, buff=0.2)
        self.play(FadeIn(scrub, shift=UP * 0.1), run_time=0.7)
        self.wait(4.5)

        # punchline swap
        punch = Text("This question can't be answered by a textbook — it needs this lecture.",
                     font="Helvetica", color=WHITE).scale(0.34)
        punch.move_to(scrub.get_center())
        self.play(FadeOut(scrub, shift=DOWN * 0.1),
                  FadeIn(punch, shift=DOWN * 0.1), run_time=0.8)
        self.wait(5.5)

        self.play(FadeOut(VGroup(heading, player, time_lbl, board, eq_line1, eq_line2,
                                 bar_bg, bar_fg, head, q_grp, punch)), run_time=0.8)

    # ═══════════════════════════════════════════════════════════════════
    # 3  HOW IT WORKS — brief pipeline, timestamp-aware retrieval
    # ═══════════════════════════════════════════════════════════════════
    def _scene_pipeline(self) -> None:
        heading = Text("How EduVidQA works", font="Helvetica", weight="BOLD",
                       color=WHITE).scale(0.52).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.7)

        # ── timeline ──
        tl_label = Text("Lecture timeline", font="Helvetica", color=MUTED).scale(0.28)
        tl_label.shift(UP * 2.5 + LEFT * 4.0)
        tl = Line(LEFT * 5.5, RIGHT * 5.5, color=GREY_D, stroke_width=3).shift(UP * 2.0)
        marks = VGroup()
        mark_times = ["0:00", "10:00", "20:00", "30:00", "40:00", "48:12"]
        for i, t in enumerate(mark_times):
            x = -5.5 + i * (11.0 / 5)
            tick = Line(UP * 0.08, DOWN * 0.08, color=GREY_D, stroke_width=2).shift(UP * 2.0 + RIGHT * x)
            lbl = Text(t, font="Helvetica", color=MUTED).scale(0.18).next_to(tick, DOWN, buff=0.06)
            marks.add(tick, lbl)

        self.play(FadeIn(tl_label), Create(tl), run_time=0.8)
        self.play(FadeIn(marks), run_time=0.5)

        # ── question marker at ~32:40 ──
        q_x = -5.5 + (32.67 / 48.2) * 11.0  # proportional
        q_marker = Dot(color=GOLD, radius=0.12).move_to(UP * 2.0 + RIGHT * q_x)
        q_lbl = Text("32:40", font="Helvetica", weight="BOLD", color=GOLD).scale(0.24)
        q_lbl.next_to(q_marker, UP, buff=0.12)
        self.play(GrowFromCenter(q_marker), FadeIn(q_lbl), run_time=0.6)
        self.wait(0.5)

        # ── retrieved chunks light up near the question ──
        chunk_times = [30.17, 32.67, 34.08, 36.30]
        chunk_labels = ["30:10", "32:40", "34:05", "36:18"]
        chunk_dots = VGroup()
        chunk_lbls = VGroup()
        for ct, cl in zip(chunk_times, chunk_labels):
            cx = -5.5 + (ct / 48.2) * 11.0
            d = Dot(color=ACCENT, radius=0.09).move_to(UP * 2.0 + RIGHT * cx)
            l = Text(cl, font="Helvetica", color=ACCENT).scale(0.18).next_to(d, DOWN, buff=0.18)
            chunk_dots.add(d)
            chunk_lbls.add(l)

        retrieve_lbl = Text("Retrieve nearest chunks to 32:40",
                            font="Helvetica", color=ACCENT).scale(0.3)
        retrieve_lbl.shift(UP * 0.8)
        self.play(FadeIn(retrieve_lbl, shift=UP * 0.1), run_time=0.6)
        self.play(*[GrowFromCenter(d) for d in chunk_dots],
                  *[FadeIn(l) for l in chunk_lbls], run_time=0.9)
        self.wait(1.0)

        # ── pipeline nodes below ──
        n_frame = _node("Live Frame", "what's on screen at 32:40", color=GOLD, w=2.8)
        n_chunks = _node("Top-K Chunks", "transcript near that time", color=ACCENT, w=2.8)
        n_llm = _node("Vision LLM", "reads frame + text, answers", color=OK, w=2.8)

        pipe = VGroup(n_frame, n_chunks, n_llm).arrange(RIGHT, buff=0.8).shift(DOWN * 0.7)

        a1 = _arrow_lr(n_frame, n_chunks)
        a2 = _arrow_lr(n_chunks, n_llm)

        # arrows from timeline dots down to chunks node
        feed_arrows = VGroup()
        for d in chunk_dots:
            fa = Arrow(d.get_bottom() + DOWN * 0.2, n_chunks.get_top() + UP * 0.05,
                       buff=0.05, stroke_width=1.5, color=ACCENT,
                       max_tip_length_to_length_ratio=0.08)
            feed_arrows.add(fa)

        # arrow from q_marker down to frame node
        frame_arrow = Arrow(q_marker.get_bottom() + DOWN * 0.2, n_frame.get_top() + UP * 0.05,
                            buff=0.05, stroke_width=2, color=GOLD,
                            max_tip_length_to_length_ratio=0.08)

        self.play(FadeIn(n_frame, shift=UP * 0.15), GrowArrow(frame_arrow), run_time=0.8)
        self.play(FadeIn(n_chunks, shift=UP * 0.15),
                  *[GrowArrow(fa) for fa in feed_arrows], run_time=0.9)
        self.play(GrowArrow(a1), run_time=0.5)
        self.play(FadeIn(n_llm, shift=UP * 0.15), GrowArrow(a2), run_time=0.8)
        self.wait(0.8)

        # ── answer emerges ──
        ans_box = _box(3.2, 1.0, color=OK, fill="#1A2320")
        ans_box.next_to(n_llm, DOWN, buff=0.6)
        ans_t1 = Text("Answer + citations", font="Helvetica", weight="BOLD",
                       color=WHITE).scale(0.28)
        ans_t2 = Text("[30:10]  [32:40]  [34:05]  [36:18]", font="Helvetica",
                       color=GOLD).scale(0.24)
        ans_content = VGroup(ans_t1, ans_t2).arrange(DOWN, buff=0.08).move_to(ans_box.get_center())
        ans_arr = Arrow(n_llm.get_bottom(), ans_box.get_top(), buff=0.08, stroke_width=2.5,
                        color=OK, max_tip_length_to_length_ratio=0.1)

        self.play(GrowArrow(ans_arr), DrawBorderThenFill(ans_box),
                  FadeIn(ans_content), run_time=0.9)
        self.play(Indicate(ans_t2, color=GOLD, scale_factor=1.15), run_time=0.8)
        self.wait(4.5)

        # ── tech stack caption ──
        tech = Text(
            "yt-dlp · Whisper · Jina CLIP · Chroma · Groq Llama-4-Scout / Gemini Flash",
            font="Helvetica", color=MUTED,
        ).scale(0.22).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(tech), run_time=0.6)
        self.wait(4.0)

        all_pipe = VGroup(heading, tl_label, tl, marks, q_marker, q_lbl,
                          chunk_dots, chunk_lbls, retrieve_lbl,
                          n_frame, n_chunks, n_llm, a1, a2,
                          feed_arrows, frame_arrow,
                          ans_box, ans_content, ans_arr, tech)
        self.play(FadeOut(all_pipe), run_time=0.8)

    # ═══════════════════════════════════════════════════════════════════
    # 4  SPLIT-SCREEN: ChatGPT vs EduVidQA — the USP killer moment
    # ═══════════════════════════════════════════════════════════════════
    def _scene_splitscreen(self) -> None:
        heading = Text("Why not just use ChatGPT?", font="Helvetica", weight="BOLD",
                       color=WHITE).scale(0.55).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # divider
        divider = DashedVMobject(
            Line(UP * 2.0, DOWN * 2.8, color=GREY_D, stroke_width=2), num_dashes=14,
        )
        self.play(Create(divider), run_time=0.6)

        # ── LEFT: ChatGPT panel ──
        l_title = Text("ChatGPT", font="Helvetica", weight="BOLD",
                       color=MUTED).scale(0.38).shift(LEFT * 3.5 + UP * 1.8)
        l_box = _box(5.5, 3.0, color=GREY_D, fill="#1A1A1E")
        l_box.shift(LEFT * 3.5 + DOWN * 0.3)
        l_q = Text('"Which example did the prof use for the chain rule?"',
                   font="Helvetica", color=WHITE).scale(0.24)
        l_q.move_to(l_box.get_top() + DOWN * 0.4)

        l_a1 = Text("Back-propagation uses the chain rule to compute",
                     font="Helvetica", color=MUTED).scale(0.22)
        l_a2 = Text("gradients layer by layer. A common example is",
                     font="Helvetica", color=MUTED).scale(0.22)
        l_a3 = Text("the XOR problem, where...",
                     font="Helvetica", color=MUTED).scale(0.22)
        l_ans = VGroup(l_a1, l_a2, l_a3).arrange(DOWN, buff=0.08, aligned_edge=LEFT)
        l_ans.next_to(l_q, DOWN, buff=0.35).align_to(l_q, LEFT).shift(RIGHT * 0.15)

        l_verdict_box = RoundedRectangle(
            corner_radius=0.1, width=4.0, height=0.55,
            stroke_color=FAIL, stroke_width=2, fill_color="#2A1A1A", fill_opacity=1,
        )
        l_verdict = Text("Generic. Not from THIS lecture.",
                         font="Helvetica", color=FAIL).scale(0.24)
        l_verdict.move_to(l_verdict_box.get_center())
        l_verdict_grp = VGroup(l_verdict_box, l_verdict)
        l_verdict_grp.next_to(l_ans, DOWN, buff=0.35)

        self.play(FadeIn(l_title), DrawBorderThenFill(l_box), run_time=0.7)
        self.play(FadeIn(l_q, shift=UP * 0.1), run_time=0.6)
        self.play(FadeIn(l_ans), run_time=0.8)
        self.wait(0.8)
        self.play(FadeIn(l_verdict_grp, shift=UP * 0.1), run_time=0.7)
        self.wait(2.5)

        # ── RIGHT: EduVidQA panel ──
        r_title = Text("EduVidQA", font="Helvetica", weight="BOLD",
                       color=ACCENT).scale(0.38).shift(RIGHT * 3.5 + UP * 1.8)
        r_box = _box(5.5, 3.0, color=ACCENT, fill="#141E28")
        r_box.shift(RIGHT * 3.5 + DOWN * 0.3)
        r_q = Text('"Which example did the prof use for the chain rule?"',
                   font="Helvetica", color=WHITE).scale(0.24)
        r_q.move_to(r_box.get_top() + DOWN * 0.4)

        r_a1 = Text('At [32:40] the professor draws dL/dw = dL/dy · dy/dw',
                     font="Helvetica", color=WHITE).scale(0.22)
        r_a2 = Text("and says 'this is where the gradient flows backward.'",
                     font="Helvetica", color=WHITE).scale(0.22)
        r_a3 = Text("At [34:05] he works through the XOR network as a",
                     font="Helvetica", color=WHITE).scale(0.22)
        r_a4 = Text("concrete example of that rule.",
                     font="Helvetica", color=WHITE).scale(0.22)
        r_ans = VGroup(r_a1, r_a2, r_a3, r_a4).arrange(DOWN, buff=0.07, aligned_edge=LEFT)
        r_ans.next_to(r_q, DOWN, buff=0.3).align_to(r_q, LEFT).shift(RIGHT * 0.15)

        r_ts = Text("Sources: [32:40]  ·  [34:05]  ·  [36:18]",
                     font="Helvetica", color=GOLD).scale(0.24)
        r_ts.next_to(r_ans, DOWN, buff=0.2).align_to(r_ans, LEFT)

        self.play(FadeIn(r_title), DrawBorderThenFill(r_box), run_time=0.7)
        self.play(FadeIn(r_q, shift=UP * 0.1), run_time=0.5)
        self.play(FadeIn(r_a1), run_time=0.6)
        self.play(FadeIn(r_a2), run_time=0.6)
        self.play(FadeIn(r_a3), run_time=0.5)
        self.play(FadeIn(r_a4), run_time=0.5)
        self.play(FadeIn(r_ts), run_time=0.6)
        self.wait(0.5)

        # highlight timestamps
        self.play(Indicate(r_ts, color=GOLD, scale_factor=1.12), run_time=0.9)

        r_verdict_box = RoundedRectangle(
            corner_radius=0.1, width=4.6, height=0.55,
            stroke_color=OK, stroke_width=2, fill_color="#1A2A1A", fill_opacity=1,
        )
        r_verdict = Text("Grounded. Verifiable. Click to jump.",
                         font="Helvetica", color=OK).scale(0.24)
        r_verdict.move_to(r_verdict_box.get_center())
        r_verdict_grp = VGroup(r_verdict_box, r_verdict)
        r_verdict_grp.next_to(r_ts, DOWN, buff=0.2)
        self.play(FadeIn(r_verdict_grp, shift=UP * 0.1), run_time=0.7)
        self.wait(1.0)

        # dim left, glow right
        self.play(l_box.animate.set_opacity(0.3), l_ans.animate.set_opacity(0.3),
                  l_q.animate.set_opacity(0.3), l_verdict_grp.animate.set_opacity(0.3),
                  l_title.animate.set_opacity(0.3),
                  run_time=0.8)

        # punchline
        usp = Text("Every answer is traceable to a moment in the lecture.",
                    font="Helvetica", weight="BOLD", color=WHITE).scale(0.38)
        usp.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(usp, shift=UP * 0.15), run_time=0.9)
        self.wait(6.5)

        all_split = VGroup(heading, divider,
                           l_title, l_box, l_q, l_ans, l_verdict_grp,
                           r_title, r_box, r_q, r_ans, r_ts, r_verdict_grp,
                           usp)
        self.play(FadeOut(all_split), run_time=0.8)

    # ═══════════════════════════════════════════════════════════════════
    # 5  CTA
    # ═══════════════════════════════════════════════════════════════════
    def _scene_cta(self) -> None:
        headline = Text("Any lecture. Any doubt. Any time.",
                        font="Helvetica", weight="BOLD", color=WHITE).scale(0.7)
        headline.shift(UP * 1.0)
        self.play(FadeIn(headline, shift=DOWN * 0.2), run_time=1.0)

        bullets = VGroup(
            Text("Grounded answers — not hallucinated textbook quotes",
                 font="Helvetica", color=MUTED).scale(0.36),
            Text("Timestamp citations — click to jump to the exact moment",
                 font="Helvetica", color=MUTED).scale(0.36),
            Text("Works on any YouTube lecture, no retraining needed",
                 font="Helvetica", color=MUTED).scale(0.36),
        ).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        bullets.next_to(headline, DOWN, buff=0.6)
        for b in bullets:
            self.play(FadeIn(b, shift=RIGHT * 0.15), run_time=0.5)
        self.wait(1.0)

        brand = VGroup(
            Dot(color=ACCENT, radius=0.14),
            Text("EduVidQA", font="Helvetica", weight="BOLD", color=WHITE).scale(0.65),
        ).arrange(RIGHT, buff=0.2)
        brand.next_to(bullets, DOWN, buff=0.7)
        self.play(FadeIn(brand, shift=UP * 0.15), run_time=0.8)
        self.wait(12.0)
        self.play(FadeOut(VGroup(headline, bullets, brand)), run_time=0.8)
        self.wait(0.3)
