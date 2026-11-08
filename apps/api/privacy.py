"""Privacy helpers. Phone numbers are masked before they reach logs, the database or the UI."""
from __future__ import annotations

import re

_DIGITS = re.compile(r"\D")
_PHONE_IN_TEXT = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{4})[\s-]?(\d{5})(?!\d)")


def mask_phone(phone: str | None) -> str | None:
    """'+91 98123 45610' -> '98XXXXXX10'. Keeps the first two and last two digits."""
    if not phone:
        return None
    digits = _DIGITS.sub("", phone)
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) < 6:
        return "X" * len(digits) if digits else None
    return digits[:2] + "X" * (len(digits) - 4) + digits[-2:]


def is_masked(phone: str | None) -> bool:
    return phone is None or bool(re.fullmatch(r"\d{2}X+\d{2}", phone))


def mask_phones_in_text(text: str) -> str:
    """Mask any Indian mobile number spoken or typed inside free text (transcripts, notes)."""
    return _PHONE_IN_TEXT.sub(lambda m: mask_phone(m.group(1) + m.group(2)) or "", text)
