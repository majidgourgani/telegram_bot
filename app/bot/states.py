"""Conversation states.

Unlike the original script (which used one state per question), questions are
now dynamic — a single ``QUESTION`` state tracks progress via ``user_data``, so
the admin can add or remove questions without changing any state wiring.
"""

from __future__ import annotations

from enum import IntEnum


class State(IntEnum):
    MENU = 0
    CHECK_MEMBERSHIP = 1
    ASK_CONSENT = 2
    ASK_FIRST_NAME = 3
    ASK_LAST_NAME = 4
    ASK_PHONE = 5
    QUESTION = 6
