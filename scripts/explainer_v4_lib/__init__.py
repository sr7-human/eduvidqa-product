"""Shared helpers for EduVidQA Kitchen-Tour explainer (v4).

All 15 scenes import from here. Keep public surface stable.
"""

from .palette import (
    BG,
    MAITRE,
    QUILL,
    LENS,
    INDIE,
    VEE,
    CRITIC,
    CUSTOMER,
)
from .floorplan import RestaurantFloorplan
from .pi_chef import (
    PiChef,
    make_maitre,
    make_quill,
    make_lens,
    make_indie,
    make_vee,
    make_critic,
    make_customer,
)
from .order_ticket import OrderTicket
from .speech_bubble import SpeechBubble, lower_third_label
from .base_scene import BaseScene

__all__ = [
    "BG",
    "MAITRE",
    "QUILL",
    "LENS",
    "INDIE",
    "VEE",
    "CRITIC",
    "CUSTOMER",
    "RestaurantFloorplan",
    "PiChef",
    "make_maitre",
    "make_quill",
    "make_lens",
    "make_indie",
    "make_vee",
    "make_critic",
    "make_customer",
    "OrderTicket",
    "SpeechBubble",
    "lower_third_label",
    "BaseScene",
]
