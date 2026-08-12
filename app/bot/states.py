"""Conversation states.

Questions are dynamic — a single ``QUESTION`` state tracks progress via
``user_data`` — and the name is collected in one step, so there is no separate
first/last-name or consent state.
"""

from __future__ import annotations

from enum import IntEnum


class State(IntEnum):
    MENU = 0
    CHECK_MEMBERSHIP = 1
    ASK_NAME = 2
    ASK_PHONE = 3
    QUESTION = 4
