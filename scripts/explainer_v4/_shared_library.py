"""Library/embedding mobjects shared by Session B scenes (2, 3, 4, 8).

This file is owned by Session B only. Other sessions must not modify it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    Arrow,
    Rectangle,
    Square,
    Text,
    VGroup,
    YELLOW,
)

# allow `from explainer_v4_lib import ...` when manim is launched from repo root
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))


# ── Corkboard (Scene 3 — keyframe pinboard, reused as backdrop in 4) ─────
class Corkboard(VGroup):
    """A pinboard with `rows × cols` slots for keyframe thumbnails."""

    def __init__(
        self,
        rows: int = 2,
        cols: int = 3,
        cell_w: float = 1.10,
        cell_h: float = 0.80,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.rows = rows
        self.cols = cols
        self.cell_w = cell_w
        self.cell_h = cell_h

        board = Rectangle(
            width=cols * cell_w + 0.35,
            height=rows * cell_h + 0.45,
            stroke_color="#A0703A",
            stroke_width=2,
            fill_color="#5C3A1E",
            fill_opacity=0.92,
        )
        self._board = board
        self.add(board)

        title = Text("Keyframes", color="#F0E0C0").scale(0.20)
        title.next_to(board.get_top(), np.array([0, -1, 0]), buff=0.10)
        self._title = title
        self.add(title)

        self.cells = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                cx = (c - (cols - 1) / 2) * cell_w
                cy = ((rows - 1) / 2 - r) * cell_h - 0.08
                slot = Square(
                    side_length=min(cell_w, cell_h) * 0.78,
                    stroke_color="#3A2010",
                    stroke_width=0.6,
                    fill_color="#3A2010",
                    fill_opacity=0.30,
                )
                slot.move_to(board.get_center() + np.array([cx, cy, 0]))
                row_cells.append(slot)
                self.add(slot)
            self.cells.append(row_cells)

    def slot_position(self, r: int, c: int):
        """Live world-space center of slot (r, c) — tracks the corkboard
        even after it's been moved/scaled by the caller."""
        return self.cells[r][c].get_center()


# ── DrawerWall (Scenes 4, 8 — vector library) ─────────────────────────────
class DrawerWall(VGroup):
    """Grid of `n_rows × n_cols` tiny drawers representing vector slots."""

    def __init__(
        self,
        n_rows: int = 8,
        n_cols: int = 12,
        cell: float = 0.32,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.cell = cell

        self.drawers: list[list[Square]] = []
        for r in range(n_rows):
            row = []
            for c in range(n_cols):
                cx = (c - (n_cols - 1) / 2) * cell
                cy = ((n_rows - 1) / 2 - r) * cell
                d = Square(
                    side_length=cell * 0.92,
                    stroke_color="#7A6440",
                    stroke_width=0.6,
                    fill_color="#1F1A12",
                    fill_opacity=0.85,
                )
                d.move_to(np.array([cx, cy, 0]))
                row.append(d)
                self.add(d)
            self.drawers.append(row)

        frame = Rectangle(
            width=n_cols * cell + 0.20,
            height=n_rows * cell + 0.20,
            stroke_color="#A38A55",
            stroke_width=1.6,
            fill_opacity=0,
        )
        self.add(frame)

        cap = Text("Vector Library", color="#E5D4A1").scale(0.22)
        cap.next_to(frame, np.array([0, 1, 0]), buff=0.10)
        self.add(cap)

    def drawer(self, r: int, c: int) -> Square:
        return self.drawers[r][c]


# ── vector_arrow_from (Scenes 4, 8) ───────────────────────────────────────
def vector_arrow_from(
    source_mobject,
    target_drawer,
    coord_text: str = "[0.12, -0.44, 0.81, ...]",
    color=YELLOW,
):
    """Build a glowing arrow + coord label going source → target_drawer.

    Returns ``(arrow, coord_label)``. Caller plays whatever animation it likes
    (e.g. ``GrowArrow(arrow)``, ``FadeIn(coord_label)``).
    """
    start = source_mobject.get_center()
    end = target_drawer.get_center()
    arrow = Arrow(
        start=start,
        end=end,
        color=color,
        stroke_width=3,
        buff=0.05,
        max_tip_length_to_length_ratio=0.10,
    )
    coord = Text(coord_text, color=color).scale(0.18)
    midpoint = (np.array(start) + np.array(end)) / 2
    coord.move_to(midpoint + np.array([0, 0.30, 0]))
    return arrow, coord
