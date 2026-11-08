# Generated from packages/shared/schemas by `make types`. Do not edit.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Customer(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    name: str | None = None
    phone: Annotated[str | None, Field(pattern='^[0-9]{2}X+[0-9]{2}$')] = None


class Line(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    item: str
    qty: Annotated[int, Field(ge=1)]
    mods: list[str]
    station: str
    note: str | None = None


class Kot(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kot_no: Annotated[str, Field(pattern='^K-[0-9]+$')]
    order_id: Annotated[str, Field(pattern='^ORD-[0-9]+$')]
    channel: Literal['dine_in', 'phone', 'takeaway']
    created_at: Annotated[
        str,
        Field(
            description='ISO 8601 in UTC, for example 2026-10-11T13:42:08Z.',
            pattern='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$',
        ),
    ]
    customer: Customer
    stations: Annotated[
        list[str],
        Field(description='Station names in the order they appear in `lines`.'),
    ]
    lines: Annotated[list[Line], Field(min_length=1)]
    notes: str
    total: Annotated[int, Field(ge=0)]
