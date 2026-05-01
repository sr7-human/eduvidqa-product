"""Restaurant floorplan VGroup with named sub-positions."""

from __future__ import annotations

import numpy as np
from manim import Line, Rectangle, VGroup

from .palette import FLOOR_LINE, ZONE_STROKE


def _zone(x0: float, x1: float, y0: float, y1: float) -> Rectangle:
    w = x1 - x0
    h = y1 - y0
    rect = Rectangle(
        width=w,
        height=h,
        stroke_color=ZONE_STROKE,
        stroke_width=0,
        stroke_opacity=0,
        fill_opacity=0,
    )
    rect.move_to(np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0]))
    return rect


class RestaurantFloorplan(VGroup):
    """Continuous floorplan: pantry → library → kitchen → dining table."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # zone rectangles (floor projection on dark bg)
        floor_y0, floor_y1 = -3.4, 1.6
        pantry_zone  = _zone(-6.0, -2.5, floor_y0, floor_y1)
        library_zone = _zone(-2.5,  1.5, floor_y0, floor_y1)
        kitchen_zone = _zone( 1.5,  5.0, floor_y0, floor_y1)
        table_zone   = _zone(-1.6, 1.6, -3.6, -2.4)

        # subtle floor baseline
        floor = Line(
            np.array([-6.0, floor_y0, 0]),
            np.array([5.0, floor_y0, 0]),
            stroke_color=FLOOR_LINE,
            stroke_width=0.8,
            stroke_opacity=0.3,
        )

        self.add(floor, pantry_zone, library_zone, kitchen_zone, table_zone)

        # named anchor points (centres of each zone, at floor level)
        self.pantry  = np.array([-4.25, -2.5, 0])
        self.library = np.array([-0.5,  -2.5, 0])
        self.kitchen = np.array([ 3.25, -2.5, 0])
        self.table   = np.array([ 0.0,  -3.0, 0])
