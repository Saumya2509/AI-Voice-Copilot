"""SQLite tables. Money is stored as integer paise (columns ending in `_paise`).

Timestamps are naive datetimes in UTC.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

CATEGORY_KINDS = ("starter", "main", "bread", "rice", "dessert", "beverage", "side")
CHANNELS = ("dine_in", "phone", "takeaway")
DAYPARTS = ("breakfast", "lunch", "snack", "dinner")
POS_STATUSES = ("pending", "sent", "acked", "failed", "needs_attention")


class Category(SQLModel, table=True):
    __tablename__ = "categories"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    kind: str


class Item(SQLModel, table=True):
    __tablename__ = "items"
    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    name: str = Field(index=True, unique=True)
    price_paise: int
    food_cost_paise: int
    veg: bool = True
    spice_level: int = 0  # 0 none, 1 mild, 2 medium, 3 hot
    prep_minutes: int = 10
    available: bool = True
    station: str = "curry"  # tandoor | curry | wok | grill | cold | beverage | dessert
    aliases_json: str = "[]"
    description: Optional[str] = None
    image_url: Optional[str] = None
    cost_estimated: bool = Field(default=False, sa_column_kwargs={"server_default": "0"})  # cost from a default %


class ModifierGroup(SQLModel, table=True):
    __tablename__ = "modifier_groups"
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="items.id", index=True)
    name: str  # Size | Spice | Add-ons
    required: bool = False
    min_select: int = 0
    max_select: int = 1


class Modifier(SQLModel, table=True):
    __tablename__ = "modifiers"
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="modifier_groups.id", index=True)
    name: str
    price_delta_paise: int = 0
    cost_delta_paise: int = 0


class Order(SQLModel, table=True):
    __tablename__ = "orders"
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(index=True)
    channel: str
    subtotal_paise: int
    discount_paise: int = 0
    total_paise: int
    covers: int = 1
    daypart: str
    external_ref: Optional[str] = Field(default=None, index=True)  # order id from an imported PoS export
    customer_name: Optional[str] = Field(default=None, index=True)
    upsell_added_paise: int = Field(default=0, sa_column_kwargs={"server_default": "0"})  # added by accepted offers


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    item_id: int = Field(foreign_key="items.id", index=True)
    qty: int
    unit_price_paise: int
    unit_cost_paise: int
    modifiers_json: str = "[]"


class Ingredient(SQLModel, table=True):
    __tablename__ = "ingredients"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    unit: str
    stock: float
    reorder_level: float


class RecipeLine(SQLModel, table=True):
    __tablename__ = "recipe_lines"
    item_id: int = Field(foreign_key="items.id", primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredients.id", primary_key=True)
    qty: float


class Call(SQLModel, table=True):
    __tablename__ = "calls"
    id: str = Field(primary_key=True)
    started_at: datetime
    ended_at: Optional[datetime] = None
    language: Optional[str] = None
    outcome: Optional[str] = None  # ordered | abandoned | transferred
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
    upsell_shown: int = 0
    upsell_accepted: int = 0
    transcript_json: str = "[]"  # phone numbers masked before storage
    events_json: str = "[]"      # server events in order, for call replay
    recording_path: Optional[str] = None  # file name under data/recordings
    recording_bytes: Optional[int] = None
    duration_s: Optional[float] = None


class UpsellRule(SQLModel, table=True):
    __tablename__ = "upsell_rules"
    id: Optional[int] = Field(default=None, primary_key=True)
    anchor_item_id: int = Field(foreign_key="items.id", index=True)
    offer_item_id: int = Field(foreign_key="items.id")
    daypart: Optional[str] = None
    alpha: float = 1.0
    beta: float = 1.0
    lift: float = 0.0
    confidence: float = 0.0
    support: float = 0.0


class UpsellEvent(SQLModel, table=True):
    __tablename__ = "upsell_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    call_id: str = Field(foreign_key="calls.id", index=True)
    rule_id: Optional[int] = Field(default=None, foreign_key="upsell_rules.id")
    item_id: int = Field(foreign_key="items.id")
    shown_at: datetime
    accepted: Optional[bool] = None
    reason_json: str = "{}"


class PosOrder(SQLModel, table=True):
    __tablename__ = "pos_orders"
    id: Optional[int] = Field(default=None, primary_key=True)
    idempotency_key: str = Field(unique=True, index=True)
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id", index=True)
    payload_json: str
    status: str = "pending"
    kot_no: Optional[str] = None
    kot_json: Optional[str] = None
    attempts: int = 0
    sent_at: Optional[datetime] = None
    ack_at: Optional[datetime] = None
    error: Optional[str] = None


class AppSetting(SQLModel, table=True):
    """Key-value settings (upsell policy, kitchen busy flag, language packs, combo offer pool)."""
    __tablename__ = "app_settings"
    key: str = Field(primary_key=True)
    value_json: str


class PriceChange(SQLModel, table=True):
    """Log of prices applied from the pricing lab."""
    __tablename__ = "price_changes"
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="items.id", index=True)
    old_price_paise: int
    new_price_paise: int
    applied_at: datetime
    source: str = "pricing_lab"
