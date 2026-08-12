"""Small, pure helpers for the bot."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

_EN_TO_FA = {ord(e): p for e, p in zip("0123456789", "۰۱۲۳۴۵۶۷۸۹")}


def to_persian_digits(value) -> str:
    """Convert ASCII digits in ``value`` to Persian digits."""
    return str(value).translate(_EN_TO_FA)


def round_half_up(value: float) -> int:
    """Round to the nearest integer, halves going up (not banker's rounding)."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ENGLISH_DIGITS = "0123456789"

_DIGIT_TRANSLATION = {
    **{ord(p): ord(e) for p, e in zip(_PERSIAN_DIGITS, _ENGLISH_DIGITS)},
    **{ord(a): ord(e) for a, e in zip(_ARABIC_DIGITS, _ENGLISH_DIGITS)},
}


def normalize_phone_number(phone: str) -> str:
    """Normalise Persian/Arabic digits and validate a 7–15 digit phone.

    Returns the cleaned number, or ``""`` if invalid.
    """
    phone = phone.translate(_DIGIT_TRANSLATION)
    phone = re.sub(r"[()\s-]", "", phone)

    if not re.fullmatch(r"\+?\d{7,15}", phone):
        return ""

    return phone
