"""EduVidQA integrated explainer (v3) — Manim Community 0.20.1.

Run:
    manim -ql scripts/explainer_v3.py EduVidQAExplainer          # 480p15
    manim -qm scripts/explainer_v3.py EduVidQAExplainer          # 720p30
    manim -qh scripts/explainer_v3.py EduVidQAExplainer          # 1080p60

6-scene integrated pitch. USP = timestamp-grounded answers. No time limit.
Combines the polished UI of v2 (timeline, split-screen) with a deeper
pipeline walkthrough inspired by v1 (Ingest / Index / Ask).
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
    Text,
    Transform,
    VGroup,
    Write,
    rate_functions,
)

# ── palette ──────────────────────────────────────────────────────────
BG     = "#0E1116"
ACCENT = "#4FC3F7"   # cyan       — EduVidQA primary
GOLD   = "#FFD54F"   # amber      — highlights / timestamps
OK     = "#81C784"   # green      — success / answer
FAIL   = "#EF5350"   # red        — problem / scrubbing
MUTED  = "#9AA0A6"   # grey       — captions


# ── helpers ──────────────────────────────────────────────────────────
def _box(w: float, h: float, color: str = GREY_D, fill: str = "#1A1D22") -> RoundedRectangle:
    return RoundedRectangle(
        corner_radius=0.15, width=w, height=h,
        stroke_color=color, stroke_width=2, fill_color=fill, fill_opacity=1,
    )


def _node(title: str, sub: str, color: str = ACCENT,
          w: float = 2.6, h: float = 1.0) -> VGroup:
    box = RoundedRectangle(
        corner_radius=0.15, width=w, height=h,
        stroke_color=color, stroke_width=2.5, fill_color=BG, fill_opacity=0.92,
    )
    t = Text(title, font="Helvetica", weight="BOLD", color=WHITE).scale(0.3)
    s = Text(sub, font="Helvetica", color=MUTED).scale(0.22)
    t.next_to(box.get_center(), UP, buff=0.04)
    s.next_to(t, DOWN, buff=0.06)
    return VGroup(box, t, s)


def _arrow_lr(a, b, color: str = GREY_B) -> Arrow:
    return Arrow(a.get_right(), b.get_left(), buff=0.1, stroke_width=3,
                 max_tip_length_to_length_ratio=0.12, color=color)


def _section_card(title: str, color: str = ACCENT) -> VGroup:
    """A large chapter card that sits centre-screen for ~1s between scenes."""
    ribbon = Rectangle(width=4.8, height=0.08, fill_color=color, fill_opacity=1,
                       stroke_width=0)
    t = Text(title, font="Helvetica", weight="BOLD", color=WHITE).scale(0.9)
    t.next_to(ribbon, UP, buff=0.35)
    ribbon.next_to(t, DOWN, buff=0.35)
    return VGroup(t, ribbon)


class EduVidQAExplainer(Scene):
    def construct(self) -> None:
        self.camera.background_color = BG

        self._scene_title()        # ~14 s
        self._scene_problem()      # ~28 s
        self._scene_overview()     # ~30 s
        self._scene_ingest_index() # ~40 s
        self._scene_ask()          # ~36 s
        self._scene_splitscreen()  # ~44 s
        self._scene_cta()          # ~18 s
        # Total target: ~210 s (3:30)

    # ═══════════════════════════════════════════════════════════════════
    # 1 · TITLE
    # ═══════════════════════════════════════════════════════════════════
    def _scene_title(self) -> None:
        dot = Dot(color=ACCENT, radius=0.2).shift(LEFT * 2.3)
        title = Text("EduVidQA", font="Helvetica", weight="BOLD",
                     color=WHITE).scale(1.3).next_to(dot, RIGHT, buff=0.3)
        tagline = Text(
            "Ask a lecture video — get answers grounded in the exact moment.",
            font="Helvetica", color=MUTED,
        ).scale(0.4).next_to(VGroup(dot, title), DOWN, buff=0.45)

        self.play(GrowFromCenter(dot), run_time=0.6)
        self.play(FadeIn(title, shift=RIGHT * 0.3), run_time=0.9)
        self.play(FadeIn(tagline, shift=UP * 0.15), run_time=0.9)
        self.play(Indicate(dot, color=GOLD, scale_factor=1.6), run_time=0.9)
        self.wait(1.0)

        # dual audience line
        aud1 = Text("For students who pause lectures at 2 AM —",
                    font="Helvetica", color=WHITE).scale(0.38)
        aud2 = Text("and for builders who want to see how it works.",
                    font="Helvetica", color=ACCENT).scale(0.38)
        aud = VGroup(aud1, aud2).arrange(DOWN, buff=0.15)
        aud.next_to(tagline, DOWN, buff=0.6)
        self.play(FadeIn(aud1, shift=UP * 0.1), run_time=0.7)
        self.play(FadeIn(aud2, shift=UP * 0.1), run_time=0.7)
        self.wait(3.5)

        self.play(FadeOut(VGroup(dot, title, tagline, aud)), run_time=0.8)

    # ═══════════════════════════════════════════════════════════════════
    # 2 · THE PROBLEM — a question only THIS lecture can answer
    # ═══════════════════════════════════════════════════════════════════
    def _scene_problem(self) -> None:
        heading = Text("2 AM. No TA. A doubt at 32:40.",
                       font="Helvetica", weight="BOLD", color=WHITE).scale(0.55)
        heading.to_edge(UP, buff=0.6)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # ── mock player ──────────────────────────────────────────────
        player = _box(6.0, 3.0).shift(UP * 0.3)
        time_lbl = Text("32:40 / 48:12", font="Helvetica",
                        color=MUTED).scale(0.28)
        time_lbl.move_to(player.get_top() + DOWN * 0.22)

        board = Rectangle(width=4.8, height=1.6, stroke_width=0,
                          fill_color="#2B2D30", fill_opacity=1)
        board.move_to(player.get_center() + UP * 0.15)
        eq1 = Text("dL/dw  =  dL/dy · dy/dw", font="Courier",
                   color=WHITE).scale(0.36)
        eq1.move_to(board.get_center() + UP * 0.22)
        eq2 = Text('"the gradient flows backward"', font="Helvetica",
                   color=GOLD).scale(0.26).next_to(eq1, DOWN, buff=0.15)

        bar_bg = Line(player.get_left() + RIGHT * 0.3 + DOWN * 1.3,
                      player.get_right() + LEFT * 0.3 + DOWN * 1.3,
                      color=GREY_D, stroke_width=4)
        bar_fg = Line(bar_bg.get_start(),
                      bar_bg.get_start() + RIGHT * 3.6,
                      color=FAIL, stroke_width=4)
        head = Dot(bar_fg.get_end(), color=FAIL, radius=0.08)

        self.play(DrawBorderThenFill(player), FadeIn(time_lbl), run_time=0.9)
        self.play(FadeIn(board), FadeIn(eq1), FadeIn(eq2), run_time=0.9)
        self.play(Create(bar_bg), Create(bar_fg), FadeIn(head), run_time=0.6)
        self.wait(0.8)

        # ── lecture-specific question ────────────────────────────────
        q_box = _box(6.0, 0.85, color=GOLD)
        q_l1 = Text('"Which example did the professor use',
                    font="Helvetica", color=WHITE).scale(0.28)
        q_l2 = Text('to explain the chain rule here?"',
                    font="Helvetica", color=WHITE).scale(0.28)
        q_content = VGroup(q_l1, q_l2).arrange(DOWN, buff=0.06)
        q_content.move_to(q_box.get_center())
        q_grp = VGroup(q_box, q_content).next_to(player, DOWN, buff=0.3)
        self.play(FadeIn(q_grp, shift=UP * 0.2), run_time=0.8)
        self.wait(1.8)

        # scrubbing
        for x in [2.0, 4.5, 1.4, 3.8, 2.2]:
            end = bar_bg.get_start() + RIGHT * x
            self.play(head.animate.move_to(end),
                      bar_fg.animate.put_start_and_end_on(bar_bg.get_start(), end),
                      run_time=0.4, rate_func=rate_functions.ease_in_out_sine)

        scrub = Text("7 minutes scrubbing. Doubt still unclear.",
                     font="Helvetica", color=MUTED).scale(0.36)
        scrub.next_to(q_grp, DOWN, buff=0.22)
        self.play(FadeIn(scrub, shift=UP * 0.1), run_time=0.7)
        self.wait(3.5)

        punch = Text("This question can't be answered by a textbook — it needs this lecture.",
                     font="Helvetica", color=WHITE).scale(0.34)
        punch.move_to(scrub.get_center())
        self.play(FadeOut(scrub, shift=DOWN * 0.1),
                  FadeIn(punch, shift=DOWN * 0.1), run_time=0.8)
        self.wait(4.5)

        self.play(FadeOut(VGroup(heading, player, time_lbl, board, eq1, eq2,
                                 bar_bg, bar_fg, head, q_grp, punch)),
                  run_time=0.8)

    # ═══════════════════════════════════════════════════════════════════
    # 3 · PIPELINE OVERVIEW — Ingest → Index → Ask
    # ═══════════════════════════════════════════════════════════════════
    def _scene_overview(self) -> None:
        heading = Text("Three stages, end to end.",
                       font="Helvetica", weight="BOLD", color=WHITE).scale(0.55)
        heading.to_edge(UP, buff=0.6)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        ingest = _node("INGEST", "watch + read the video", color=ACCENT,
                       w=3.0, h=1.2)
        index = _node("INDEX", "turn it into searchable memory", color=GOLD,
                      w=3.0, h=1.2)
        ask = _node("ASK", "retrieve + answer a doubt", color=OK,
                    w=3.0, h=1.2)

        row = VGroup(ingest, index, ask).arrange(RIGHT, buff=1.1).shift(UP * 0.2)
        a1 = _arrow_lr(ingest, index)
        a2 = _arrow_lr(index, ask)

        # "once per video" vs "per question" labels
        once_br = Line(ingest.get_corner([-1, -1, 0]) + DOWN * 0.3,
                       index.get_corner([1, -1, 0]) + DOWN * 0.3,
                       color=MUTED, stroke_width=2)
        once_lbl = Text("once per video", font="Helvetica", color=MUTED,
                        slant="ITALIC").scale(0.26)
        once_lbl.next_to(once_br, DOWN, buff=0.1)

        per_br = Line(ask.get_corner([-1, -1, 0]) + DOWN * 0.3,
                      ask.get_corner([1, -1, 0]) + DOWN * 0.3,
                      color=MUTED, stroke_width=2)
        per_lbl = Text("per question", font="Helvetica", color=MUTED,
                       slant="ITALIC").scale(0.26)
        per_lbl.next_to(per_br, DOWN, buff=0.1)

        self.play(FadeIn(ingest, shift=UP * 0.2), run_time=0.7)
        self.play(GrowArrow(a1), FadeIn(index, shift=UP * 0.2), run_time=0.8)
        self.play(GrowArrow(a2), FadeIn(ask, shift=UP * 0.2), run_time=0.8)
        self.wait(0.5)
        self.play(Create(once_br), FadeIn(once_lbl), run_time=0.7)
        self.play(Create(per_br), FadeIn(per_lbl), run_time=0.7)
        self.wait(1.5)

        # explain each in one line
        explainers = VGroup(
            Text("INGEST  — download, transcribe, extract keyframes",
                 font="Helvetica", color=ACCENT).scale(0.3),
            Text("INDEX   — embed everything, store in a vector database",
                 font="Helvetica", color=GOLD).scale(0.3),
            Text("ASK     — search the index, let an LLM answer with citations",
                 font="Helvetica", color=OK).scale(0.3),
        ).arrange(DOWN, buff=0.15, aligned_edge=LEFT)
        explainers.next_to(per_lbl, DOWN, buff=0.5)
        # ensure horizontal centering
        explainers.set_x(0)

        for e in explainers:
            self.play(FadeIn(e, shift=RIGHT * 0.15), run_time=0.7)
        self.wait(4.5)

        self.play(FadeOut(VGroup(heading, ingest, index, ask, a1, a2,
                                 once_br, once_lbl, per_br, per_lbl,
                                 explainers)), run_time=0.9)

    # ═══════════════════════════════════════════════════════════════════
    # 4 · INGEST + INDEX zoom
    # ═══════════════════════════════════════════════════════════════════
    def _scene_ingest_index(self) -> None:
        heading = Text("Stage 1 + 2 — teach the system the lecture",
                       font="Helvetica", weight="BOLD", color=WHITE).scale(0.48)
        heading.to_edge(UP, buff=0.55)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # source tile: YouTube mp4
        src = _box(2.2, 1.0, color=ACCENT)
        src.shift(LEFT * 5.2 + UP * 0.3)
        src_t = Text("YouTube", font="Helvetica", weight="BOLD",
                     color=WHITE).scale(0.3)
        src_s = Text(".mp4 @ 360p", font="Helvetica", color=MUTED).scale(0.22)
        src_g = VGroup(src_t, src_s).arrange(DOWN, buff=0.05).move_to(src.get_center())
        self.play(DrawBorderThenFill(src), FadeIn(src_g), run_time=0.8)

        # three outputs: transcript, keyframes, chunks
        t_node = _node("Transcript", "Whisper if captions missing",
                       color=ACCENT, w=2.6, h=1.0)
        k_node = _node("Keyframes", "1 fps + SSIM 0.92 dedup",
                       color=ACCENT, w=2.6, h=1.0)
        c_node = _node("Chunks", "10-second windows",
                       color=ACCENT, w=2.6, h=1.0)
        stack = VGroup(t_node, k_node, c_node).arrange(DOWN, buff=0.25)
        stack.move_to(LEFT * 1.0 + UP * 0.3)

        arr_t = Arrow(src.get_right(), t_node.get_left(), buff=0.08,
                      stroke_width=2, color=GREY_B,
                      max_tip_length_to_length_ratio=0.1)
        arr_k = Arrow(src.get_right(), k_node.get_left(), buff=0.08,
                      stroke_width=2, color=GREY_B,
                      max_tip_length_to_length_ratio=0.1)
        arr_c = Arrow(src.get_right(), c_node.get_left(), buff=0.08,
                      stroke_width=2, color=GREY_B,
                      max_tip_length_to_length_ratio=0.1)

        self.play(GrowArrow(arr_t), FadeIn(t_node, shift=RIGHT * 0.15), run_time=0.7)
        self.play(GrowArrow(arr_k), FadeIn(k_node, shift=RIGHT * 0.15), run_time=0.7)
        self.play(GrowArrow(arr_c), FadeIn(c_node, shift=RIGHT * 0.15), run_time=0.7)
        self.wait(1.6)

        # embedding step — cross-modal
        embed = _node("Jina CLIP", "text + images → shared vectors",
                      color=GOLD, w=2.8, h=1.0)
        embed.move_to(RIGHT * 2.6 + UP * 0.3)

        arrs_to_embed = VGroup(
            Arrow(t_node.get_right(), embed.get_left(), buff=0.08,
                  stroke_width=2, color=GREY_B,
                  max_tip_length_to_length_ratio=0.1),
            Arrow(k_node.get_right(), embed.get_left(), buff=0.08,
                  stroke_width=2, color=GREY_B,
                  max_tip_length_to_length_ratio=0.1),
            Arrow(c_node.get_right(), embed.get_left(), buff=0.08,
                  stroke_width=2, color=GREY_B,
                  max_tip_length_to_length_ratio=0.1),
        )
        self.play(*[GrowArrow(a) for a in arrs_to_embed],
                  FadeIn(embed, shift=RIGHT * 0.15), run_time=0.9)
        self.wait(0.8)

        # vector DB
        db = _node("Vector DB", "Chroma · searchable memory",
                   color=GOLD, w=2.8, h=1.0)
        db.move_to(RIGHT * 5.4 + UP * 0.3)
        db_arr = _arrow_lr(embed, db, color=GOLD)
        self.play(GrowArrow(db_arr), FadeIn(db, shift=RIGHT * 0.15), run_time=0.8)

        # cross-modal insight caption
        insight = Text(
            "Cross-modal: a text query can retrieve a matching image — and vice versa.",
            font="Helvetica", color=GOLD,
        ).scale(0.3).to_edge(DOWN, buff=1.0)
        self.play(FadeIn(insight, shift=UP * 0.1), run_time=0.8)
        self.play(Indicate(insight, color=GOLD, scale_factor=1.05), run_time=0.8)
        self.wait(3.0)

        # tech caption
        tech = Text(
            "yt-dlp · pytubefix · Whisper · ffmpeg · Jina CLIP v2 · Chroma",
            font="Helvetica", color=MUTED,
        ).scale(0.24).to_edge(DOWN, buff=0.35)
        self.play(FadeIn(tech), run_time=0.6)
        self.wait(3.5)

        self.play(FadeOut(VGroup(heading, src, src_g, t_node, k_node, c_node,
                                 arr_t, arr_k, arr_c,
                                 embed, arrs_to_embed, db, db_arr,
                                 insight, tech)), run_time=0.9)

    # ═══════════════════════════════════════════════════════════════════
    # 5 · ASK zoom — timeline + retrieval + VLM
    # ═══════════════════════════════════════════════════════════════════
    def _scene_ask(self) -> None:
        heading = Text("Stage 3 — answer a doubt, with receipts",
                       font="Helvetica", weight="BOLD", color=WHITE).scale(0.48)
        heading.to_edge(UP, buff=0.55)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        # ── timeline at top ──────────────────────────────────────────
        tl_label = Text("Lecture timeline", font="Helvetica", color=MUTED).scale(0.26)
        tl_label.shift(UP * 2.55 + LEFT * 4.3)
        tl = Line(LEFT * 5.5, RIGHT * 5.5, color=GREY_D, stroke_width=3).shift(UP * 2.05)
        marks = VGroup()
        for i, t in enumerate(["0:00", "10:00", "20:00", "30:00", "40:00", "48:12"]):
            x = -5.5 + i * (11.0 / 5)
            tick = Line(UP * 0.08, DOWN * 0.08, color=GREY_D, stroke_width=2)
            tick.shift(UP * 2.05 + RIGHT * x)
            lbl = Text(t, font="Helvetica", color=MUTED).scale(0.18)
            lbl.next_to(tick, DOWN, buff=0.08)
            marks.add(tick, lbl)
        self.play(FadeIn(tl_label), Create(tl), FadeIn(marks), run_time=0.9)

        # question marker
        q_x = -5.5 + (32.67 / 48.2) * 11.0
        q_marker = Dot(color=GOLD, radius=0.13).move_to(UP * 2.05 + RIGHT * q_x)
        q_lbl = Text("? 32:40", font="Helvetica", weight="BOLD",
                     color=GOLD).scale(0.24).next_to(q_marker, UP, buff=0.12)
        self.play(GrowFromCenter(q_marker), FadeIn(q_lbl), run_time=0.7)
        self.wait(0.4)

        # retrieved chunks near question (timestamp-proximity re-rank)
        chunk_times = [30.17, 32.67, 34.08, 36.30]
        chunk_labels = ["30:10", "32:40", "34:05", "36:18"]
        chunk_dots = VGroup()
        chunk_lbls = VGroup()
        for ct, cl in zip(chunk_times, chunk_labels):
            cx = -5.5 + (ct / 48.2) * 11.0
            d = Dot(color=ACCENT, radius=0.1).move_to(UP * 2.05 + RIGHT * cx)
            l = Text(cl, font="Helvetica", color=ACCENT).scale(0.18)
            l.next_to(d, DOWN, buff=0.22)
            chunk_dots.add(d)
            chunk_lbls.add(l)

        retr_lbl = Text("Retrieve nearest chunks to 32:40",
                        font="Helvetica", color=ACCENT).scale(0.3)
        retr_lbl.shift(UP * 1.55)
        self.play(FadeIn(retr_lbl, shift=UP * 0.1), run_time=0.6)
        self.play(*[GrowFromCenter(d) for d in chunk_dots],
                  *[FadeIn(l) for l in chunk_lbls], run_time=0.9)
        self.wait(1.5)
        # clear the retrieve label before drawing arrows that would cross it
        self.play(FadeOut(retr_lbl), run_time=0.4)

        # ── three inputs → VLM → answer ──────────────────────────────
        n_frame = _node("Live Frame", "what's on screen @ 32:40",
                        color=GOLD, w=2.8, h=1.0)
        n_chunks = _node("Top-K Chunks", "transcript near that time",
                         color=ACCENT, w=2.8, h=1.0)
        n_digest = _node("Lecture Digest", "one-page summary",
                         color=ACCENT, w=2.8, h=1.0)

        inputs = VGroup(n_frame, n_chunks, n_digest).arrange(RIGHT, buff=0.5)
        inputs.shift(DOWN * 0.25)

        # arrows from timeline down to input nodes
        frame_arrow = Arrow(q_marker.get_bottom() + DOWN * 0.05,
                             n_frame.get_top() + UP * 0.05,
                             buff=0.05, stroke_width=2, color=GOLD,
                             max_tip_length_to_length_ratio=0.08)
        chunk_arrows = VGroup()
        for d in chunk_dots:
            fa = Arrow(d.get_bottom() + DOWN * 0.05,
                       n_chunks.get_top() + UP * 0.05,
                       buff=0.05, stroke_width=1.3, color=ACCENT,
                       max_tip_length_to_length_ratio=0.08)
            chunk_arrows.add(fa)

        self.play(FadeIn(n_frame, shift=UP * 0.15), GrowArrow(frame_arrow),
                  run_time=0.8)
        self.play(FadeIn(n_chunks, shift=UP * 0.15),
                  *[GrowArrow(fa) for fa in chunk_arrows], run_time=0.9)
        self.play(FadeIn(n_digest, shift=UP * 0.15), run_time=0.6)
        self.wait(0.8)

        # VLM node
        vlm = _node("Vision LLM", "reads frame + text, writes answer",
                    color=OK, w=3.6, h=1.0)
        vlm.move_to(DOWN * 1.65)
        arrs_to_vlm = VGroup(
            Arrow(n_frame.get_bottom(), vlm.get_top() + LEFT * 1.0,
                  buff=0.08, stroke_width=2, color=GREY_B,
                  max_tip_length_to_length_ratio=0.1),
            Arrow(n_chunks.get_bottom(), vlm.get_top(),
                  buff=0.08, stroke_width=2, color=GREY_B,
                  max_tip_length_to_length_ratio=0.1),
            Arrow(n_digest.get_bottom(), vlm.get_top() + RIGHT * 1.0,
                  buff=0.08, stroke_width=2, color=GREY_B,
                  max_tip_length_to_length_ratio=0.1),
        )
        self.play(*[GrowArrow(a) for a in arrs_to_vlm],
                  FadeIn(vlm, shift=UP * 0.15), run_time=0.9)
        self.wait(0.8)

        # answer card
        ans_box = _box(5.0, 0.95, color=OK, fill="#1A2320")
        ans_box.to_edge(DOWN, buff=0.55)
        ans_t1 = Text("Answer + citations", font="Helvetica",
                      weight="BOLD", color=WHITE).scale(0.28)
        ans_t2 = Text("[30:10]  [32:40]  [34:05]  [36:18]",
                      font="Helvetica", color=GOLD).scale(0.26)
        ans_content = VGroup(ans_t1, ans_t2).arrange(DOWN, buff=0.08)
        ans_content.move_to(ans_box.get_center())
        ans_arr = Arrow(vlm.get_bottom(), ans_box.get_top(),
                        buff=0.08, stroke_width=2.5, color=OK,
                        max_tip_length_to_length_ratio=0.1)
        self.play(GrowArrow(ans_arr), DrawBorderThenFill(ans_box),
                  FadeIn(ans_content), run_time=0.9)
        self.play(Indicate(ans_t2, color=GOLD, scale_factor=1.15), run_time=0.9)
        self.wait(4.5)

        all_ask = VGroup(heading, tl_label, tl, marks, q_marker, q_lbl,
                         chunk_dots, chunk_lbls,
                         n_frame, n_chunks, n_digest,
                         frame_arrow, chunk_arrows,
                         vlm, arrs_to_vlm, ans_box, ans_content, ans_arr)
        self.play(FadeOut(all_ask), run_time=0.9)

    # ═══════════════════════════════════════════════════════════════════
    # 6 · SPLIT-SCREEN — ChatGPT vs EduVidQA (the USP)
    # ═══════════════════════════════════════════════════════════════════
    def _scene_splitscreen(self) -> None:
        heading = Text("Why not just use ChatGPT?", font="Helvetica",
                       weight="BOLD", color=WHITE).scale(0.55)
        heading.to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.2), run_time=0.8)

        divider = DashedVMobject(
            Line(UP * 2.0, DOWN * 2.8, color=GREY_D, stroke_width=2),
            num_dashes=14,
        )
        self.play(Create(divider), run_time=0.6)

        # LEFT panel ───────────────────────────────────────────────────
        l_title = Text("ChatGPT", font="Helvetica", weight="BOLD",
                       color=MUTED).scale(0.4).shift(LEFT * 3.5 + UP * 1.75)
        l_box = _box(5.5, 3.0, color=GREY_D, fill="#1A1A1E")
        l_box.shift(LEFT * 3.5 + DOWN * 0.35)
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

        l_vbox = RoundedRectangle(corner_radius=0.1, width=4.0, height=0.55,
                                  stroke_color=FAIL, stroke_width=2,
                                  fill_color="#2A1A1A", fill_opacity=1)
        l_v = Text("Generic. Not from THIS lecture.",
                   font="Helvetica", color=FAIL).scale(0.24)
        l_v.move_to(l_vbox.get_center())
        l_verdict = VGroup(l_vbox, l_v).next_to(l_ans, DOWN, buff=0.35)

        self.play(FadeIn(l_title), DrawBorderThenFill(l_box), run_time=0.7)
        self.play(FadeIn(l_q, shift=UP * 0.1), run_time=0.6)
        self.play(FadeIn(l_ans), run_time=0.8)
        self.wait(0.8)
        self.play(FadeIn(l_verdict, shift=UP * 0.1), run_time=0.7)
        self.wait(2.0)

        # RIGHT panel ──────────────────────────────────────────────────
        r_title = Text("EduVidQA", font="Helvetica", weight="BOLD",
                       color=ACCENT).scale(0.4).shift(RIGHT * 3.5 + UP * 1.75)
        r_box = _box(5.5, 3.0, color=ACCENT, fill="#141E28")
        r_box.shift(RIGHT * 3.5 + DOWN * 0.35)
        r_q = Text('"Which example did the prof use for the chain rule?"',
                   font="Helvetica", color=WHITE).scale(0.24)
        r_q.move_to(r_box.get_top() + DOWN * 0.4)
        r_a1 = Text("At [32:40] the professor draws dL/dw = dL/dy · dy/dw",
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
        self.play(Indicate(r_ts, color=GOLD, scale_factor=1.12), run_time=0.9)

        r_vbox = RoundedRectangle(corner_radius=0.1, width=4.6, height=0.55,
                                  stroke_color=OK, stroke_width=2,
                                  fill_color="#1A2A1A", fill_opacity=1)
        r_v = Text("Grounded. Verifiable. Click to jump.",
                   font="Helvetica", color=OK).scale(0.24)
        r_v.move_to(r_vbox.get_center())
        r_verdict = VGroup(r_vbox, r_v).next_to(r_ts, DOWN, buff=0.2)
        self.play(FadeIn(r_verdict, shift=UP * 0.1), run_time=0.7)
        self.wait(1.5)

        # dim left
        self.play(l_box.animate.set_opacity(0.3),
                  l_ans.animate.set_opacity(0.3),
                  l_q.animate.set_opacity(0.3),
                  l_verdict.animate.set_opacity(0.3),
                  l_title.animate.set_opacity(0.3),
                  run_time=0.8)

        usp = Text("Every answer is traceable to a moment in the lecture.",
                   font="Helvetica", weight="BOLD", color=WHITE).scale(0.42)
        usp.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(usp, shift=UP * 0.15), run_time=0.9)
        self.wait(5.5)

        all_split = VGroup(heading, divider,
                           l_title, l_box, l_q, l_ans, l_verdict,
                           r_title, r_box, r_q, r_ans, r_ts, r_verdict,
                           usp)
        self.play(FadeOut(all_split), run_time=0.9)

    # ═══════════════════════════════════════════════════════════════════
    # 7 · CTA
    # ═══════════════════════════════════════════════════════════════════
    def _scene_cta(self) -> None:
        headline = Text("Any lecture. Any doubt. Any time.",
                        font="Helvetica", weight="BOLD", color=WHITE).scale(0.75)
        headline.shift(UP * 1.1)
        self.play(FadeIn(headline, shift=DOWN * 0.2), run_time=1.0)

        bullets = VGroup(
            Text("Grounded answers — not hallucinated textbook quotes",
                 font="Helvetica", color=MUTED).scale(0.38),
            Text("Timestamp citations — click to jump to the exact moment",
                 font="Helvetica", color=MUTED).scale(0.38),
            Text("Works on any YouTube lecture, no retraining needed",
                 font="Helvetica", color=MUTED).scale(0.38),
        ).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        bullets.next_to(headline, DOWN, buff=0.7)
        for b in bullets:
            self.play(FadeIn(b, shift=RIGHT * 0.15), run_time=0.55)
        self.wait(1.2)

        brand = VGroup(
            Dot(color=ACCENT, radius=0.16),
            Text("EduVidQA", font="Helvetica", weight="BOLD", color=WHITE).scale(0.7),
        ).arrange(RIGHT, buff=0.22)
        brand.next_to(bullets, DOWN, buff=0.7)
        self.play(FadeIn(brand, shift=UP * 0.15), run_time=0.9)
        self.wait(6.0)
        self.play(FadeOut(VGroup(headline, bullets, brand)), run_time=0.9)
        self.wait(0.4)
