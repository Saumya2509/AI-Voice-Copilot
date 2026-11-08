# Generated from packages/shared/schemas by `make types`. Do not edit.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Customer(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    name: Annotated[str | None, Field(max_length=80)] = None
    phone: Annotated[
        str | None,
        Field(
            description='Masked: first two and last two digits visible.',
            pattern='^[0-9]{2}X+[0-9]{2}$',
        ),
    ] = None
    address: Annotated[str | None, Field(max_length=300)] = None


class Upsell(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    shown: Annotated[int, Field(ge=0, le=2)]
    accepted: Annotated[int, Field(ge=0, le=2)]
    added_revenue: Annotated[int, Field(ge=0)]
    added_margin: int


class Modifier(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    group: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]
    price_delta: int


class Line(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    item_id: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(min_length=1)]
    qty: Annotated[int, Field(ge=1, le=50)]
    unit_price: Annotated[int, Field(ge=0)]
    modifiers: list[Modifier]
    notes: Annotated[str, Field(max_length=200)]
    source: Annotated[
        Literal['customer', 'upsell', 'combo', 'staff'],
        Field(
            description='customer: said by the caller; upsell or combo: an accepted offer; staff: added by hand from the menu.'
        ),
    ]
    upsell_rule_id: int | None = None


class Order(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    order_id: Annotated[str, Field(pattern='^ORD-[0-9]+$')]
    call_id: Annotated[str | None, Field(min_length=1)] = None
    channel: Literal['dine_in', 'phone', 'takeaway']
    language: Literal['en', 'hi', 'hinglish', 'mr', 'gu']
    customer: Customer
    lines: Annotated[list[Line], Field(min_length=1)]
    subtotal: Annotated[int, Field(ge=0)]
    discount: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=0)]
    upsell: Upsell
    confirmed_at: Annotated[
        str,
        Field(
            description='ISO 8601 in UTC, for example 2026-10-11T13:42:08Z.',
            pattern='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$',
        ),
    ]
