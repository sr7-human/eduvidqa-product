"""Simplified SM-2 spaced repetition algorithm."""
from __future__ import annotations

_EASE_FLOOR = 1.3


def sm2_update(
    is_correct: bool,
    repetitions: int,
    ease_factor: float,
    interval_days: int,
) -> tuple[int, float, int]:
    """Compute next (repetitions, ease_factor, interval_days) after a review.

    Simplified SM-2:
    - Correct: rep += 1; interval grows (1 -> 6 -> interval * EF); EF += 0.1
    - Wrong: rep = 0; interval = 1; EF -= 0.2
    - EF is clamped to a floor of 1.3.
    """
    if is_correct:
        repetitions += 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = max(1, int(interval_days * ease_factor))
        ease_factor = max(_EASE_FLOOR, ease_factor + 0.1)
    else:
        repetitions = 0
        interval_days = 1
        ease_factor = max(_EASE_FLOOR, ease_factor - 0.2)
    return repetitions, ease_factor, interval_days
