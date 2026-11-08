"""Kitchen order ticket (KOT) builder. Lines are grouped by station."""
from __future__ import annotations

from schemas import Kot, KotCustomer, KotLine, OrderPayload

# Order in which stations appear on the ticket: hot food first, then cold and drinks.
STATION_ORDER = ["tandoor", "curry", "wok", "grill", "cold", "dessert", "beverage"]


def format_modifier(group: str, name: str) -> str:
    if group == "Spice":
        return name if name.lower().endswith("spicy") else f"{name} spicy"
    if group == "Add-ons":
        return f"+ {name}"
    return name


def build_kot(order: OrderPayload, stations: dict[int, str], kot_no: str, created_at: str) -> Kot:
    """`stations` maps item_id to its kitchen station."""
    lines: list[KotLine] = []
    order_notes: list[str] = []
    for line in order.lines:
        note = line.notes.strip()
        lines.append(
            KotLine(
                item=line.name,
                qty=line.qty,
                mods=[format_modifier(m.group, m.name) for m in line.modifiers],
                station=stations.get(line.item_id, "curry"),
                note=note or None,
            )
        )
        if note:
            order_notes.append(f"{line.name}: {note}")

    rank = {s: i for i, s in enumerate(STATION_ORDER)}
    lines.sort(key=lambda l: rank.get(l.station, len(rank)))  # stable: keeps call order within a station
    stations_seen: list[str] = []
    for l in lines:
        if l.station not in stations_seen:
            stations_seen.append(l.station)
    return Kot(
        kot_no=kot_no,
        order_id=order.order_id,
        channel=order.channel,
        created_at=created_at,
        customer=KotCustomer(name=order.customer.name, phone=order.customer.phone),
        stations=stations_seen,
        lines=lines,
        notes="; ".join(order_notes),
        total=order.total,
    )


def render_text(kot: Kot) -> str:
    """Plain-text ticket for a thermal printer."""
    channel = kot.channel.replace("_", " ").upper()
    out = [f"KOT {kot.kot_no}   {kot.order_id}   {channel}", kot.created_at]
    if kot.customer.name or kot.customer.phone:
        out.append(" ".join(p for p in (kot.customer.name, kot.customer.phone) if p))
    for station in kot.stations:
        out.append(f"--- {station.upper()} ---")
        for l in (x for x in kot.lines if x.station == station):
            out.append(f"{l.qty:>3} x {l.item}")
            out.extend(f"      {m}" for m in l.mods)
            if l.note:
                out.append(f"      NOTE: {l.note}")
    if kot.notes:
        out.append(f"Notes: {kot.notes}")
    return "\n".join(out)
