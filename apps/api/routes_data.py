"""Analytics, CSV upload and public menu endpoints (improve.md, section 9)."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select

import db
import settings
import upload
from models import Category, Item
from money import rupees
from revenue import analytics as an
from revenue.engine import get_engine
from routes_revenue import ApiError

router = APIRouter(prefix="/api/v1")


def filters(
    date_from: Optional[str] = Query(None, alias="from", description="Restaurant-local date, YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, alias="to"),
    category: Optional[str] = Query(None, description="Category name"),
    veg: Optional[str] = Query(None, pattern="^(veg|non_veg)$"),
    channel: Optional[str] = Query(None, pattern="^(dine_in|phone|takeaway)$"),
    weekday: Optional[int] = Query(None, ge=0, le=6, description="0 is Monday"),
    hour: Optional[int] = Query(None, ge=0, le=23),
) -> an.Filters:
    for d in (date_from, date_to):
        if d:
            try:
                from datetime import date
                date.fromisoformat(d)
            except ValueError:
                raise ApiError(422, "invalid_date", f"'{d}' is not a date. Use YYYY-MM-DD.")
    return an.Filters(date_from, date_to, category, veg, channel, weekday, hour)


def _view(f: an.Filters):
    eng = get_engine()
    data = eng.data()
    return data, an.view(data, f)


def _money_fields(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        r = dict(r)
        for k in list(r):
            if k.endswith("_paise"):
                r[k.removesuffix("_paise")] = rupees(r.pop(k))
        out.append(r)
    return out


@router.get("/analytics/overview")
def analytics_overview(f: an.Filters = Depends(filters)):
    data, v = _view(f)
    o = an.overview(v)
    return {**v.meta(f), "revenue": rupees(o["revenue_paise"]), "orders": o["orders"], "aov": rupees(o["aov_paise"]),
            "items_sold": o["items_sold"], "gross_margin_pct": o["gross_margin_pct"], "busiest_hour": o["busiest_hour"],
            "data_from": None if data.orders.empty else an._local(data.orders["ts"]).dt.date.min().isoformat(),
            "data_to": None if data.orders.empty else an._local(data.orders["ts"]).dt.date.max().isoformat()}


@router.get("/analytics/category-share")
def analytics_category_share(f: an.Filters = Depends(filters)):
    _data, v = _view(f)
    return {**v.meta(f), "categories": _money_fields(an.category_share(v))}


@router.get("/analytics/veg-split")
def analytics_veg_split(f: an.Filters = Depends(filters)):
    _data, v = _view(f)
    return {**v.meta(f), "slices": _money_fields(an.veg_split(v))}


@router.get("/analytics/class-split")
def analytics_class_split(f: an.Filters = Depends(filters)):
    data, v = _view(f)
    return {**v.meta(f), "classes": an.class_split(an.item_table(v, data))}


@router.get("/analytics/top-items")
def analytics_top_items(f: an.Filters = Depends(filters), by: str = Query("units", pattern="^(units|profit|revenue)$"),
                        limit: int = Query(10, ge=1, le=50)):
    data, v = _view(f)
    return {**v.meta(f), "by": by, "items": _money_fields(an.top_items(an.item_table(v, data), by, limit))}


@router.get("/analytics/trend")
def analytics_trend(f: an.Filters = Depends(filters), grain: str = Query("day", pattern="^(day|week)$")):
    _data, v = _view(f)
    return {**v.meta(f), "grain": grain, "points": _money_fields(an.trend(v, grain))}


@router.get("/analytics/heatmap")
def analytics_heatmap(f: an.Filters = Depends(filters)):
    _data, v = _view(f)
    h = an.heatmap(v)
    return {**v.meta(f), "weekdays": h["weekdays"], "max_orders": h["max_orders"], "cells": _money_fields(h["cells"])}


@router.get("/analytics/channel-mix")
def analytics_channel_mix(f: an.Filters = Depends(filters)):
    _data, v = _view(f)
    return {**v.meta(f), "channels": _money_fields(an.channel_mix(v))}


@router.get("/analytics/items")
def analytics_items(f: an.Filters = Depends(filters)):
    """Per-item figures for the margin against popularity scatter."""
    data, v = _view(f)
    t = an.item_table(v, data)
    rows = [{"item_id": int(r.item_id), "name": r.name, "category": r.category_name, "class": r.cls,
             "units": int(r.units), "revenue_paise": int(r.revenue_paise), "profit_paise": int(r.profit_paise),
             "cm_paise": int(r.cm_paise), "x": round(float(r.x), 4), "y": round(float(r.y), 4),
             "cost_estimated": bool(r.cost_estimated)} for r in t.itertuples()] if len(t) else []
    return {**v.meta(f), "popularity_factor": 0.7, "items": _money_fields(rows)}


@router.get("/analytics/lists/{kind}")
def analytics_lists(kind: str, f: an.Filters = Depends(filters)):
    if kind not in ("puzzles", "underperformers", "plowhorse_risk"):
        raise ApiError(404, "not_found", "List must be puzzles, underperformers or plowhorse_risk.")
    data, v = _view(f)
    df = an.lists(v, data, kind)
    value = {"puzzles": "potential_gain_paise", "underperformers": "removal_gain_paise",
             "plowhorse_risk": "monthly_exposure_paise"}[kind]
    rows = [{"item_id": int(r["item_id"]), "name": r["name"], "class": r["class"], "units": int(r["units"]),
             "cm_paise": int(r["cm_paise"]), "popularity_index": round(float(r["popularity_index"]), 2),
             "value_paise": int(r[value]), **({"at_risk": bool(r["at_risk"])} if kind == "plowhorse_risk" else {})}
            for _, r in df.iterrows()] if len(df) else []
    from routes_revenue import LIST_ASSUMPTIONS
    return {**v.meta(f), "kind": kind, "assumption": LIST_ASSUMPTIONS[kind], "items": _money_fields(rows)}


# ----- upload --------------------------------------------------------------------------


def _json(value: Optional[str], name: str) -> dict | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except ValueError:
        raise ApiError(422, "invalid_request", f"{name} must be a JSON object.")
    if not isinstance(data, dict):
        raise ApiError(422, "invalid_request", f"{name} must be a JSON object.")
    return data


@router.get("/import/template/{kind}")
def import_template(kind: str):
    if kind not in upload.TEMPLATES:
        raise ApiError(404, "not_found", "Templates are menu and sales.")
    return Response(upload.template_csv(kind), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={kind}.csv"})


@router.post("/import/preview")
async def import_preview(file: UploadFile = File(...), kind: str = Form("sales"), mapping: Optional[str] = Form(None),
                         session: Session = Depends(db.get_session)):
    content = await file.read()
    if kind == "sales":
        return upload.parse_sales(content, _json(mapping, "mapping"), upload.menu_lookup(session)).report("sales")
    if kind == "menu":
        from importer import import_items
        r = import_items(session, content, _json(mapping, "mapping"), None, dry_run=True).to_dict()
        return {**r, "rows": r["accepted"] + r["rejected"], "duplicates": 0, "items_found": r["accepted"],
                "orders_found": 0, "date_from": None, "date_to": None}
    raise ApiError(422, "invalid_request", "kind must be sales or menu.")


@router.post("/import/commit")
async def import_commit(file: UploadFile = File(...), kind: str = Form("sales"), mapping: Optional[str] = Form(None),
                        default_cost_pct: Optional[str] = Form(None), session: Session = Depends(db.get_session)):
    content = await file.read()
    try:
        if kind == "sales":
            return upload.commit_sales(session, content, _json(mapping, "mapping"),
                                       _json(default_cost_pct, "default_cost_pct"))
        if kind == "menu":
            return upload.commit_menu(session, content, _json(mapping, "mapping"),
                                      _json(default_cost_pct, "default_cost_pct"))
    except upload.UploadError as e:
        raise ApiError(422, e.code, e.message, e.details)
    raise ApiError(422, "invalid_request", "kind must be sales or menu.")


@router.get("/import/sample-csv")
def import_sample_csv():
    """A ready-made sales CSV for the built-in menu, to try the Analytics upload with."""
    path = settings.SAMPLES_DIR / "sample-sales.csv"
    if not path.exists():
        from seed.generate import write_sample_sales
        write_sample_sales(path)
    return FileResponse(path, media_type="text/csv", filename="sample-sales.csv")


@router.post("/import/sample")
def import_sample(session: Session = Depends(db.get_session)):
    """Replace the data with the generated sample restaurant. Clearly sample data, for exploring."""
    return upload.load_sample(session)


# ----- public menu -----------------------------------------------------------------------


@router.get("/public/menu")
def public_menu(session: Session = Depends(db.get_session)):
    cats = session.exec(select(Category).order_by(Category.id)).all()
    items = session.exec(select(Item).order_by(Item.category_id, Item.id)).all()
    by_cat: dict[int, list[Item]] = {}
    for i in items:
        by_cat.setdefault(i.category_id, []).append(i)
    return {
        "categories": [
            {"id": c.id, "name": c.name, "kind": c.kind, "items": [
                {"id": i.id, "name": i.name, "price": rupees(i.price_paise), "veg": i.veg,
                 "spice_level": i.spice_level, "description": i.description, "image_url": i.image_url,
                 "available": i.available} for i in by_cat.get(c.id, [])]}
            for c in cats if by_cat.get(c.id)
        ],
        "items": len(items),
    }
