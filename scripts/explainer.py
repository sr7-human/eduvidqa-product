"""EduVidQA explainer — Manim Community 0.20.1.

Run:
    manim -ql scripts/explainer.py EduVidQAExplainer

Target duration: ~95 seconds at 480p15 (demo for supervisor → edtech forward).
Dual-audience: every technical label is paired with a plain-English one.
"""

from __future__ import annotations

from manim import (
    BLUE_D,
    BLUE_E,
    DOWN,
    GREEN_C,
    GREY_B,
    GREY_BROWN,
    GREY_D,
    LEFT,
    ORIGIN,
    RIGHT,
    TEAL_C,
    UP,
    WHITE,
    YELLOW_D,
    Arrow,
    Circle,
    Create,
    DashedVMobject,
    Dot,
    DrawBorderThenFill,
    FadeIn,
    FadeOut,
    GrowArrow,
    GrowFromCenter,
    Indicate,
    Line,
    MathTex,
    Rectangle,
    RoundedRectangle,
    Scene,
    Text,
    Transform,
    VGroup,
    Write,
    rate_functions,
)

# ---------- palette ----------
BG = "#0E1116"
ACCENT = "#4FC3F7"   # cyan
ACCENT_2 = "#FFD54F"  # amber
OK = "#81C784"
MUTED = "#9AA0A6"


def node(title: str, subtitle: str, color: str = ACCENT, w: float = 2.6, h: float = 1.1) -> VGroup:
    """A pipeline node: rounded box with a technical title and plain-English subtitle."""
    box = RoundedRectangle(
        corner_radius=0.18, width=w, height=h,
        stroke_color=color, stroke_width=2.5, fill_color=BG, fill_opacity=0.9,
    )
    t = Text(title, font="Helvetica", weight="BOLD", color=WHITE).scale(0.32)
    s = Text(subtitle, font="Helvetica", color=MUTED).scale(0.24)
    t.next_to(box.get_center(), UP, buff=0.05)
    s.next_to(t, DOWN, buff=0.08)
    return VGroup(box, t, s)


def connector(a: VGroup, b: VGroup, color: str = GREY_B) -> Arrow:
    return Arrow(
        a.get_right(), b.get_left(),
        buff=0.12, stroke_width=3, max_tip_length_to_length_ratio=0.12,
        color=color,
    )


class EduVidQAExplainer(Scene):
    def construct(self) -> None:
        self.camera.background_color = BG

        self._scene_title()          # ~10s
        self._scene_problem()        # ~16s
        self._scene_pipeline()       # ~38s
        self._scene_demo()           # ~20s
        self._scene_outcome()        # ~12s
        # Total target: ~96s

    # ------------------------------------------------------------------
    # 1. Title + hook
    # ------------------------------------------------------------------
    def _scene_title(self) -> None:
        logo_dot = Dot(color=ACCENT, radius=0.18).shift(LEFT * 2.6)
        title = Text("EduVidQA", font="Helvetica", weight="BOLD", color=WHITE).scale(1.2)
        title.next_to(logo_dot, RIGHT, buff=0.25)
        tagline = Text(
            "Ask any lecture video — get answers grounded in the moments that matter.",
            font="Helvetica", color=MUTED,
        ).scale(0.38)
        tagline.next_to(VGroup(logo_dot, title), DOWN, buff=0.35)

        self.play(GrowFromCenter(logo_dot), run_time=0.6)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=0.9)
        self.play(FadeIn(tagline, shift=UP * 0.2), run_time=0.9)
        self.wait(1.4)

        # subtle pulse on dot
        self.play(Indicate(logo_dot, color=ACCENT_2, scale_factor=1.6), run_time=0.9)

        audience = VGroup(
            Text("For students who pause lectures —", font="Helvetica", color=WHITE).scale(0.4),
            Text("and for engineers who build the pipeline behind it.",
                 font="Helvetica", color=ACCENT).scale(0.4),
        ).arrange(DOWN, buff=0.15)
        audience.next_to(tagline, DOWN, buff=0.55)
        self.play(FadeIn(audience[0], shift=UP * 0.15), run_time=0.9)
        self.play(FadeIn(audience[1], shift=UP * 0.15), run_time=0.9)
        self.wait(4.5)

        self.play(FadeOut(VGroup(logo_dot, title, tagline, audience)), run_time=0.8)

    # ------------------------------------------------------------------
    # 2. The problem
    # ------------------------------------------------------------------
    def _scene_problem(self) -> None:
        heading = Text("The problem", font="Helvetica", weight="BOLD", color=WHITE).scale(0.55)
        heading.to_edge(UP, buff=0.6)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # Mock YouTube player
        player = RoundedRectangle(
            corner_radius=0.15, width=6.2, height=3.2,
            stroke_color=GREY_D, stroke_width=2, fill_color="#1A1D22", fill_opacity=1,
        )
        player.shift(UP * 0.35)
        screen_label = Text("Lecture · 48:12", font="Helvetica", color=MUTED).scale(0.3)
        screen_label.move_to(player.get_top() + DOWN * 0.25)

        # Fake slide content inside the player: a "neural net" sketch
        net_layers = VGroup()
        layer_xs = [-1.2, 0.0, 1.2]
        layer_counts = [3, 4, 2]
        all_nodes: list[list[Dot]] = []
        for x, n in zip(layer_xs, layer_counts):
            col = VGroup()
            col_nodes: list[Dot] = []
            for i in range(n):
                d = Dot(color=ACCENT, radius=0.07).move_to(
                    player.get_center() + [x, (i - (n - 1) / 2) * 0.28, 0]
                    + UP * 0.1
                )
                col.add(d)
                col_nodes.append(d)
            all_nodes.append(col_nodes)
            net_layers.add(col)
        edges = VGroup()
        for a_col, b_col in zip(all_nodes, all_nodes[1:]):
            for a in a_col:
                for b in b_col:
                    edges.add(Line(a.get_center(), b.get_center(),
                                   stroke_color=GREY_D, stroke_width=1))
        slide_caption = Text("Neural network — forward pass",
                             font="Helvetica", color=MUTED).scale(0.22)
        slide_caption.next_to(net_layers, DOWN, buff=0.18)

        # progress bar
        bar_bg = Line(player.get_left() + RIGHT * 0.3 + DOWN * 1.4,
                      player.get_right() + LEFT * 0.3 + DOWN * 1.4,
                      color=GREY_D, stroke_width=4)
        bar_fg = Line(bar_bg.get_start(),
                      bar_bg.get_start() + RIGHT * 2.3,
                      color="#FF5252", stroke_width=4)
        playhead = Dot(bar_fg.get_end(), color="#FF5252", radius=0.08)

        self.play(DrawBorderThenFill(player), FadeIn(screen_label), run_time=1.0)
        self.play(FadeIn(edges), FadeIn(net_layers), FadeIn(slide_caption), run_time=0.9)
        self.play(Create(bar_bg), Create(bar_fg), FadeIn(playhead), run_time=0.7)

        # Student thought bubble
        bubble = RoundedRectangle(
            corner_radius=0.25, width=4.2, height=1.0,
            stroke_color=ACCENT_2, stroke_width=2, fill_color=BG, fill_opacity=1,
        )
        q_text = Text('"Wait… what did he mean by back-propagation at 32:40?"',
                      font="Helvetica", color=WHITE).scale(0.3)
        q_text.move_to(bubble.get_center())
        bubble_group = VGroup(bubble, q_text).next_to(player, DOWN, buff=0.3)

        self.play(FadeIn(bubble_group, shift=UP * 0.2), run_time=0.9)
        self.wait(1.0)

        # Scrubbing — playhead moves back and forth, frustration
        for target_x in [0.9, 3.2, 1.6, 2.8]:
            new_end = bar_bg.get_start() + RIGHT * target_x
            self.play(
                playhead.animate.move_to(new_end),
                bar_fg.animate.put_start_and_end_on(bar_bg.get_start(), new_end),
                run_time=0.55, rate_func=rate_functions.ease_in_out_sine,
            )

        frustration = Text("Scrubbing. Re-watching. Giving up.",
                           font="Helvetica", color=MUTED).scale(0.38)
        frustration.next_to(bubble_group, DOWN, buff=0.25)
        self.play(FadeIn(frustration, shift=UP * 0.15), run_time=1.0)
        self.wait(3.0)

        punchline = Text("There has to be a better way to ask a video a question.",
                         font="Helvetica", color=WHITE).scale(0.38)
        punchline.move_to(frustration.get_center())
        self.play(FadeOut(frustration, shift=DOWN * 0.15),
                  FadeIn(punchline, shift=DOWN * 0.15), run_time=0.9)
        self.wait(4.0)
        self.play(FadeOut(punchline), run_time=0.5)

        self.play(FadeOut(VGroup(heading, player, screen_label, edges, net_layers,
                                 slide_caption, bar_bg, bar_fg,
                                 playhead, bubble_group)), run_time=0.8)

    # ------------------------------------------------------------------
    # 3. Pipeline
    # ------------------------------------------------------------------
    def _scene_pipeline(self) -> None:
        heading = Text("How EduVidQA works", font="Helvetica", weight="BOLD",
                       color=WHITE).scale(0.55).to_edge(UP, buff=0.5)
        sub = Text("A retrieval-augmented pipeline, one step at a time.",
                   font="Helvetica", color=MUTED).scale(0.34).next_to(heading, DOWN, buff=0.15)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.9)
        self.play(FadeIn(sub, shift=UP * 0.15), run_time=0.7)

        # Nodes
        n1 = node("YouTube URL", "a lecture link", color=ACCENT)
        n2 = node("Transcript + Frames", "what was said, what was shown", color=ACCENT)
        n3 = node("Chunks + Embeddings", "small pieces, turned into vectors", color=TEAL_C)
        n4 = node("Vector Index", "searchable memory (Chroma)", color=TEAL_C)
        n5 = node("Retriever", "find the right moments", color=ACCENT_2)
        n6 = node("LLM Answer", "grounded reply with timestamps", color=OK)

        top_row = VGroup(n1, n2, n3).arrange(RIGHT, buff=0.9)
        bot_row = VGroup(n6, n5, n4).arrange(RIGHT, buff=0.9)
        grid = VGroup(top_row, bot_row).arrange(DOWN, buff=1.1).shift(DOWN * 0.3)

        # technical caption under grid
        tech = Text(
            "yt-dlp  ·  Whisper  ·  ffmpeg keyframes  ·  Jina embeddings  ·  "
            "Chroma  ·  Groq Llama-4-Scout / Gemini-flash-latest",
            font="Helvetica", color=MUTED,
        ).scale(0.26).next_to(grid, DOWN, buff=0.5)

        # reveal nodes one by one with micro-captions
        micro_lines = [
            "1 · paste a link",
            "2 · extract words + visuals",
            "3 · break into chunks, embed as vectors",
            "4 · store in a vector DB",
            "5 · search for the closest chunks to the question",
            "6 · an LLM answers — with citations",
        ]
        ordered = [n1, n2, n3, n4, n5, n6]
        micro = Text("", font="Helvetica", color=ACCENT_2).scale(0.34).to_edge(DOWN, buff=0.9)

        self.play(FadeIn(ordered[0], shift=UP * 0.2), run_time=0.7)
        new = Text(micro_lines[0], font="Helvetica", color=ACCENT_2).scale(0.34).move_to(micro)
        self.play(Transform(micro, new), run_time=0.45)
        self.wait(0.7)

        # connectors for top row: n1->n2->n3
        a12 = connector(n1, n2)
        a23 = connector(n2, n3)
        self.play(FadeIn(ordered[1], shift=UP * 0.2), GrowArrow(a12), run_time=0.8)
        new = Text(micro_lines[1], font="Helvetica", color=ACCENT_2).scale(0.34).move_to(micro)
        self.play(Transform(micro, new), run_time=0.45)
        self.wait(0.8)

        self.play(FadeIn(ordered[2], shift=UP * 0.2), GrowArrow(a23), run_time=0.8)
        new = Text(micro_lines[2], font="Helvetica", color=ACCENT_2).scale(0.34).move_to(micro)
        self.play(Transform(micro, new), run_time=0.45)
        self.wait(0.9)

        # down-bend from n3 to n4
        bend = DashedVMobject(
            Line(n3.get_bottom() + DOWN * 0.05, n4.get_top() + UP * 0.05, color=GREY_B, stroke_width=3),
            num_dashes=10,
        )
        self.play(FadeIn(n4, shift=UP * 0.2), Create(bend), run_time=0.9)
        new = Text(micro_lines[3], font="Helvetica", color=ACCENT_2).scale(0.34).move_to(micro)
        self.play(Transform(micro, new), run_time=0.45)
        self.wait(0.8)

        a45 = connector(n4, n5)  # right-to-left in bottom row: arrow from n4 to n5
        # bottom row is arranged n6, n5, n4 left-to-right, so flow is n4 -> n5 -> n6 (right to left)
        a45 = Arrow(n4.get_left(), n5.get_right(), buff=0.12, stroke_width=3,
                    max_tip_length_to_length_ratio=0.12, color=GREY_B)
        self.play(FadeIn(n5, shift=UP * 0.2), GrowArrow(a45), run_time=0.8)
        new = Text(micro_lines[4], font="Helvetica", color=ACCENT_2).scale(0.34).move_to(micro)
        self.play(Transform(micro, new), run_time=0.45)
        self.wait(0.9)

        a56 = Arrow(n5.get_left(), n6.get_right(), buff=0.12, stroke_width=3,
                    max_tip_length_to_length_ratio=0.12, color=OK)
        self.play(FadeIn(n6, shift=UP * 0.2), GrowArrow(a56), run_time=0.8)
        new = Text(micro_lines[5], font="Helvetica", color=ACCENT_2).scale(0.34).move_to(micro)
        self.play(Transform(micro, new), run_time=0.45)
        self.wait(1.1)

        # reveal technical stack caption
        self.play(Write(tech), run_time=1.2)
        self.wait(1.2)

        # a travelling dot to show "a question flows through"
        path_points = [
            n5.get_top() + UP * 0.1,
            n4.get_top() + UP * 0.1,
            n4.get_center(),
            n5.get_center(),
            n6.get_center(),
        ]
        q_dot = Dot(path_points[0], color=ACCENT_2, radius=0.1)
        self.play(FadeIn(q_dot), run_time=0.3)
        for p in path_points[1:]:
            self.play(q_dot.animate.move_to(p), run_time=0.5,
                      rate_func=rate_functions.ease_in_out_sine)
        self.play(Indicate(n6, color=OK, scale_factor=1.1), FadeOut(q_dot), run_time=1.0)
        self.wait(2.2)

        # recap line
        recap = Text(
            "Plain English: paste a link → we read + watch → we remember → we search → we answer.",
            font="Helvetica", color=WHITE,
        ).scale(0.3).to_edge(DOWN, buff=0.35)
        self.play(FadeOut(micro), run_time=0.3)
        self.play(FadeIn(recap, shift=UP * 0.15), run_time=0.9)
        self.wait(4.5)
        self.play(FadeOut(recap), run_time=0.6)

        self.play(
            FadeOut(VGroup(heading, sub, grid, a12, a23, bend, a45, a56, tech)),
            run_time=0.9,
        )

    # ------------------------------------------------------------------
    # 4. Demo mock UI
    # ------------------------------------------------------------------
    def _scene_demo(self) -> None:
        heading = Text("What the user sees", font="Helvetica", weight="BOLD",
                       color=WHITE).scale(0.55).to_edge(UP, buff=0.6)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # chat window
        window = RoundedRectangle(
            corner_radius=0.2, width=9.0, height=4.6,
            stroke_color=GREY_D, stroke_width=2, fill_color="#141821", fill_opacity=1,
        ).shift(DOWN * 0.3)
        self.play(Create(window), run_time=0.8)

        # user question bubble
        q_box = RoundedRectangle(
            corner_radius=0.2, width=5.8, height=0.7,
            stroke_color=ACCENT, stroke_width=2, fill_color="#1E2A38", fill_opacity=1,
        )
        q_text = Text("What is back-propagation, exactly?",
                      font="Helvetica", color=WHITE).scale(0.34)
        q_bubble = VGroup(q_box, q_text.move_to(q_box.get_center()))
        q_bubble.move_to(window.get_top() + DOWN * 0.75 + LEFT * 1.0)
        self.play(FadeIn(q_bubble, shift=UP * 0.2), run_time=0.7)
        self.wait(0.6)

        # typing dots
        dots = VGroup(*[Dot(color=MUTED, radius=0.07) for _ in range(3)]).arrange(RIGHT, buff=0.15)
        dots.next_to(q_bubble, DOWN, buff=0.5).align_to(q_bubble, LEFT)
        self.play(FadeIn(dots), run_time=0.3)
        for _ in range(2):
            self.play(*[d.animate.shift(UP * 0.1) for d in dots], run_time=0.25)
            self.play(*[d.animate.shift(DOWN * 0.1) for d in dots], run_time=0.25)
        self.play(FadeOut(dots), run_time=0.3)

        # answer bubble
        a_box = RoundedRectangle(
            corner_radius=0.2, width=7.8, height=1.8,
            stroke_color=OK, stroke_width=2, fill_color="#1A2320", fill_opacity=1,
        )
        a_lines = VGroup(
            Text("Back-propagation is how a neural network learns from its mistakes:",
                 font="Helvetica", color=WHITE).scale(0.3),
            Text("it walks the error backward through each layer and nudges the weights.",
                 font="Helvetica", color=WHITE).scale(0.3),
            Text("Source: [32:40]  ·  [34:05]  ·  [36:18]",
                 font="Helvetica", color=ACCENT_2).scale(0.3),
        ).arrange(DOWN, buff=0.12, aligned_edge=LEFT)
        a_bubble = VGroup(a_box, a_lines.move_to(a_box.get_center()))
        a_bubble.next_to(q_bubble, DOWN, buff=0.55).align_to(window, LEFT).shift(RIGHT * 0.5)
        self.play(FadeIn(a_box), run_time=0.4)
        self.play(Write(a_lines[0]), run_time=0.9)
        self.play(Write(a_lines[1]), run_time=0.9)
        self.play(Write(a_lines[2]), run_time=0.8)
        self.wait(0.6)

        # highlight a timestamp → pulse + link annotation
        ts_highlight = a_lines[2]
        self.play(Indicate(ts_highlight, color=ACCENT_2, scale_factor=1.15), run_time=0.9)

        jump_note = Text("Click a timestamp → jump straight to that moment.",
                         font="Helvetica", color=ACCENT).scale(0.32)
        jump_note.next_to(window, DOWN, buff=0.3)
        self.play(FadeIn(jump_note, shift=UP * 0.15), run_time=0.8)
        self.wait(5.0)

        self.play(FadeOut(VGroup(heading, window, q_bubble, a_bubble, jump_note)),
                  run_time=0.9)

    # ------------------------------------------------------------------
    # 5. Outcome / CTA
    # ------------------------------------------------------------------
    def _scene_outcome(self) -> None:
        headline = Text("Any lecture. Any doubt. Any time.",
                        font="Helvetica", weight="BOLD", color=WHITE).scale(0.75)
        headline.shift(UP * 0.7)
        self.play(FadeIn(headline, shift=DOWN * 0.25), run_time=1.2)

        bullets = VGroup(
            Text("•  Grounded answers — no hallucinated textbook quotes",
                 font="Helvetica", color=MUTED).scale(0.38),
            Text("•  Timestamp citations — jump to the exact moment",
                 font="Helvetica", color=MUTED).scale(0.38),
            Text("•  Works on any YouTube lecture, in minutes",
                 font="Helvetica", color=MUTED).scale(0.38),
        ).arrange(DOWN, buff=0.2, aligned_edge=LEFT)
        bullets.next_to(headline, DOWN, buff=0.7)

        for b in bullets:
            self.play(FadeIn(b, shift=RIGHT * 0.2), run_time=0.55)
        self.wait(1.0)

        brand = VGroup(
            Dot(color=ACCENT, radius=0.14),
            Text("EduVidQA", font="Helvetica", weight="BOLD", color=WHITE).scale(0.7),
        ).arrange(RIGHT, buff=0.22)
        brand.next_to(bullets, DOWN, buff=0.7)
        self.play(FadeIn(brand, shift=UP * 0.2), run_time=0.9)
        self.wait(8.5)
        self.play(FadeOut(VGroup(headline, bullets, brand)), run_time=0.9)
        self.wait(0.4)
