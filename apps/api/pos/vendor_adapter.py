"""Template for connecting an external PoS. Same interface as the built-in PoS, plus a mapping
layer for item ids, modifiers and tax fields. Fill in the HTTP calls once the provider's API
documentation and credentials are available; until then every call raises a clear error."""
from __future__ import annotations

from dataclasses import dataclass, field

from pos.adapter import KotAck, PosAck, PosError, PosMenuItem, PosStatus
from schemas import OrderPayload


@dataclass
class VendorMapping:
    item_ids: dict[int, str] = field(default_factory=dict)      # Tadka item id -> PoS item id
    modifier_ids: dict[str, str] = field(default_factory=dict)  # "Group:Name" -> PoS modifier id
    tax_code: str | None = None                                 # PoS tax group applied to each line
    prices_include_tax: bool = True


class VendorAdapter:
    def __init__(self, base_url: str, api_key: str, outlet_id: str, mapping: VendorMapping):
        self.base_url = base_url
        self.api_key = api_key
        self.outlet_id = outlet_id
        self.mapping = mapping

    def to_vendor_payload(self, order: OrderPayload) -> dict:
        """Translate a Tadka order into the PoS request body using the mapping."""
        missing = [l.name for l in order.lines if l.item_id not in self.mapping.item_ids]
        if missing:
            raise PosError("unmapped_items", f"Map these items to PoS items first: {', '.join(missing)}.",
                           retryable=False)
        return {
            "outlet_id": self.outlet_id,
            "external_order_id": order.order_id,
            "channel": order.channel,
            "items": [
                {
                    "item_id": self.mapping.item_ids[l.item_id],
                    "quantity": l.qty,
                    "unit_price": l.unit_price,
                    "modifiers": [self.mapping.modifier_ids.get(f"{m.group}:{m.name}", m.name)
                                  for m in l.modifiers],
                    "instructions": l.notes,
                    "tax_code": self.mapping.tax_code,
                }
                for l in order.lines
            ],
            "prices_include_tax": self.mapping.prices_include_tax,
            "total": order.total,
        }

    @staticmethod
    def _not_connected():
        raise PosError("pos_not_connected", "This PoS connection is not set up yet. Use the built-in PoS, "
                       "or add the provider's API details in Settings.", retryable=False)

    def get_menu(self) -> list[PosMenuItem]:
        self._not_connected()

    def create_order(self, order: OrderPayload, idempotency_key: str) -> PosAck:
        self.to_vendor_payload(order)
        self._not_connected()

    def create_kot(self, order_id: str) -> KotAck:
        self._not_connected()

    def get_order_status(self, pos_order_id: str) -> PosStatus:
        self._not_connected()
