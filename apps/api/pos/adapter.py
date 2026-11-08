"""PoS adapter interface. Tadka talks to any point-of-sale system through this protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from schemas import Kot, OrderPayload


@dataclass(frozen=True)
class PosMenuItem:
    pos_item_id: str
    name: str
    price: int  # rupees
    available: bool


@dataclass(frozen=True)
class PosAck:
    pos_order_id: str
    status: str  # sent | acked
    duplicate: bool = False  # true when the idempotency key was seen before


@dataclass(frozen=True)
class KotAck:
    kot_no: str
    kot: Kot
    duplicate: bool = False


@dataclass(frozen=True)
class PosStatus:
    pos_order_id: str
    status: str
    kot_no: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0


class PosError(Exception):
    """Raised when the PoS cannot take the request. `retryable` says whether trying again can help."""

    def __init__(self, code: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class PosAdapter(Protocol):
    def get_menu(self) -> list[PosMenuItem]: ...
    def create_order(self, order: OrderPayload, idempotency_key: str) -> PosAck: ...
    def create_kot(self, order_id: str) -> KotAck: ...
    def get_order_status(self, pos_order_id: str) -> PosStatus: ...
