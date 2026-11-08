"""KOT models, generated from packages/shared/schemas/kot.schema.json, plus JSON helpers."""
from __future__ import annotations

from schemas._loader import errors
from schemas.generated.kot import Customer as KotCustomer, Kot as _Kot, Line as KotLine

__all__ = ["Kot", "KotCustomer", "KotLine", "validate_kot"]


class Kot(_Kot):
    def to_json_dict(self) -> dict:
        data = self.model_dump()
        for line in data["lines"]:
            if line.get("note") is None:
                line.pop("note", None)
        return data


def validate_kot(data: dict) -> list[str]:
    return errors("kot", data)
