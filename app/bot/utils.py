"""Small, pure helpers for the bot."""

from __future__ import annotations

import re

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
