from __future__ import annotations

import json

import settings
from privacy import is_masked, mask_phone, mask_phones_in_text
from schemas import OrderPayload, validate_kot, validate_order


def test_mask_phone():
    assert mask_phone("9812345610") == "98XXXXXX10"
    assert mask_phone("+91 98123 45610") == "98XXXXXX10"
    assert mask_phone("") is None
    assert is_masked("98XXXXXX10") and not is_masked("9812345610")


def test_mask_phone_in_transcript():
    text = "mera number 98123 45610 hai, aur ek dal makhani"
    assert mask_phones_in_text(text) == "mera number 98XXXXXX10 hai, aur ek dal makhani"


SAMPLE_ORDER = {
    "order_id": "ORD-8831", "call_id": "call_0192", "channel": "phone", "language": "hinglish",
    "customer": {"name": "Rohan", "phone": "98XXXXXX10", "address": None},
    "lines": [
        {"item_id": 12, "name": "Paneer Butter Masala", "qty": 1, "unit_price": 280,
         "modifiers": [{"group": "Spice", "name": "Medium", "price_delta": 0}], "notes": "no onion",
         "source": "customer"},
        {"item_id": 31, "name": "Garlic Naan", "qty": 4, "unit_price": 60, "modifiers": [], "notes": "",
         "source": "upsell", "upsell_rule_id": 77},
    ],
    "subtotal": 520, "discount": 0, "total": 520,
    "upsell": {"shown": 2, "accepted": 1, "added_revenue": 60, "added_margin": 42},
    "confirmed_at": "2026-10-11T13:42:08Z",
}


def test_spec_example_order_is_valid_and_round_trips():
    assert validate_order(SAMPLE_ORDER) == []
    assert OrderPayload.model_validate(SAMPLE_ORDER).to_json_dict() == SAMPLE_ORDER


def test_schema_rejects_unmasked_phone_and_missing_rule():
    bad = json.loads(json.dumps(SAMPLE_ORDER))
    bad["customer"]["phone"] = "9812345610"
    del bad["lines"][1]["upsell_rule_id"]
    errors = validate_order(bad)
    assert any(e.startswith("customer/phone") for e in errors)
    assert any(e.startswith("lines/1") for e in errors)


def test_spec_example_kot_is_valid():
    kot = {
        "kot_no": "K-2041", "order_id": "ORD-8831", "channel": "phone", "created_at": "2026-10-11T13:42:10Z",
        "customer": {"name": "Rohan", "phone": "98XXXXXX10"}, "stations": ["tandoor", "curry"],
        "lines": [
            {"item": "Butter Naan", "qty": 4, "mods": [], "station": "tandoor"},
            {"item": "Paneer Butter Masala", "qty": 1, "mods": ["Medium spicy"], "station": "curry",
             "note": "no onion"},
        ],
        "notes": "No onion in paneer", "total": 740,
    }
    assert validate_kot(kot) == []


def test_generated_ts_types_exist():
    types_dir = settings.REPO_ROOT / "packages" / "shared" / "types"
    order_ts = (types_dir / "order.ts").read_text(encoding="utf-8")
    assert "export interface Order" in order_ts
