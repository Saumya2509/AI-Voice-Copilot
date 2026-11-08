"""The API contract from file 08, as data, plus a tool to export the OpenAPI document.

Usage (from apps/api):  python -m contract openapi ../../packages/shared/openapi.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = "/api/v1"

# Every REST route in file 08: (method, path).
REST = [
    ("GET", "/menu"),
    ("GET", "/stats/items"),
    ("GET", "/stats/summary"),
    ("GET", "/stats/lists/{kind}"),
    ("GET", "/combos"),
    ("POST", "/combos/{combo_id}/pool"),
    ("GET", "/pricing/recommendations"),
    ("POST", "/pricing/preview"),
    ("POST", "/pricing/apply"),
    ("POST", "/calls"),
    ("GET", "/calls/{call_id}"),
    ("GET", "/orders"),
    ("GET", "/orders/{order_id}"),
    ("POST", "/orders/{order_id}/retry"),
    ("GET", "/samples"),
    ("POST", "/nlu/parse"),
    ("GET", "/settings"),
    ("PUT", "/settings"),
    ("POST", "/import/items"),
    ("POST", "/import/orders"),
    ("DELETE", "/calls"),
]
WEBSOCKET = "/ws/call/{call_id}"

# Routes from improve.md, section 9.
IMPROVE = [
    ("GET", "/import/template/{kind}"),
    ("POST", "/import/preview"),
    ("POST", "/import/commit"),
    ("POST", "/import/sample"),
    ("GET", "/analytics/overview"),
    ("GET", "/analytics/category-share"),
    ("GET", "/analytics/veg-split"),
    ("GET", "/analytics/class-split"),
    ("GET", "/analytics/top-items"),
    ("GET", "/analytics/trend"),
    ("GET", "/analytics/heatmap"),
    ("GET", "/analytics/channel-mix"),
    ("GET", "/orders/stream"),
    ("GET", "/public/menu"),
    ("GET", "/calls"),
    ("GET", "/calls/{call_id}/transcript"),
    ("GET", "/calls/{call_id}/recording"),
]

# Routes added beyond file 08 and improve.md, each documented in the README.
ADDITIONS = [
    ("GET", "/health"),
    ("POST", "/orders"),
    ("GET", "/stats/items/{item_id}/trend"),
    ("GET", "/combos/graph"),
    ("GET", "/insights"),
    ("GET", "/orders/export"),
    ("GET", "/analytics/items"),
    ("GET", "/analytics/lists/{kind}"),
    ("POST", "/calls/{call_id}/recording"),
    ("DELETE", "/calls/{call_id}/recording"),
    ("DELETE", "/calls/{call_id}"),
    ("GET", "/import/sample-csv"),
    ("GET", "/nlu/vocabulary"),
    ("GET", "/tts"),
    ("GET", "/tts/status"),
]

CLIENT_EVENTS = ["transcript.partial", "transcript.final", "ui.choice", "ui.offer", "ui.end",
                 "ui.add_item", "ui.add_combo", "ui.confirm", "ui.send", "ui.barge_in"]
SERVER_EVENTS = ["state.changed", "transcript", "nlu.result", "menu.highlight", "cart.updated", "clarify.ask",
                 "upsell.offer", "reply.say", "order.finalized", "pos.sent", "pos.ack", "error"]


def export_openapi(path: Path) -> None:
    import main

    doc = main.app.openapi()
    doc["info"]["description"] = ("Tadka API (file 08). Money is whole rupees as integers, or two-decimal strings "
                                  "where paise matter. Timestamps are ISO 8601 in UTC. Errors use "
                                  '{"error": {"code", "message", "details"}}. Live calls: WebSocket ' + WEBSOCKET + ".")
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "openapi":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        export_openapi(Path(sys.argv[2]))
    else:
        sys.exit("usage: python -m contract openapi <path>")
