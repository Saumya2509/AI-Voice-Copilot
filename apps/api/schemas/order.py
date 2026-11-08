"""Order models. The fields come from packages/shared/schemas/order.schema.json through the generated
module; this file only adds JSON helpers. Regenerate with `make types` after changing the schema."""
from __future__ import annotations

from schemas._loader import errors
from schemas.generated.order import Customer, Line as OrderLine, Modifier, Order, Upsell as UpsellSummary

__all__ = ["Customer", "Modifier", "OrderLine", "OrderPayload", "UpsellSummary", "validate_order"]


class OrderPayload(Order):
    def to_json_dict(self) -> dict:
        data = self.model_dump()
        # upsell_rule_id is only meaningful on upsold lines.
        for line in data["lines"]:
            if line.get("upsell_rule_id") is None and line["source"] != "upsell":
                line.pop("upsell_rule_id", None)
        return data


def validate_order(data: dict) -> list[str]:
    return errors("order", data)
