"""Money on the wire (file 08): whole rupees as integers, or decimal strings with two places where
paise matter. Never floats."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def rupees(paise) -> int | str:
    p = int(Decimal(str(paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if p % 100 == 0:
        return p // 100
    sign = "-" if p < 0 else ""
    return f"{sign}{abs(p) // 100}.{abs(p) % 100:02d}"
