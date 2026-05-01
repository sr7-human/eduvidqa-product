"""Base scene: dark bg + standard 14×8 camera frame."""

from __future__ import annotations

from manim import MovingCameraScene, config

from .palette import BG


class BaseScene(MovingCameraScene):
    """All Kitchen-Tour scenes inherit from this."""

    def setup(self):
        super().setup()
        config.background_color = BG
        # Projector-friendly zoom: 12 units wide (was 14 original, 10 too tight).
        self.camera.frame.set(width=12.0)
        self.camera.frame.move_to([0, 0, 0])
