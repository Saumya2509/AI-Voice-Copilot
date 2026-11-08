"""Dialogue manager (file 05, section 8).

States: GREETING, TAKING_ORDER, CLARIFYING, OFFERING, CONFIRMING, CAPTURING_DETAILS, FINALIZED, ABANDONED.

Rules enforced here:
- Never upsell while clarifying, and not before at least one item is on the order.
- At most two offers per call and one per turn. A decline ends upselling for that anchor.
- One clarification question at a time, always with two or three concrete options.
- Read back the order before finalizing.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from dialogue.templates import bjoin, en_of, hi_of, join_items, join_options, say
from nlu.language import CallLanguage
from nlu.gloss_en import gloss_en
from nlu.parser import Mention, Parse, split_fraction
from pos.service import DraftLine, DraftModifier, DraftOrder, OrderRejected
from privacy import mask_phone, mask_phones_in_text
from revenue.upsell import Offer, UpsellContext

ACTIVE = {"GREETING", "TAKING_ORDER", "CLARIFYING", "OFFERING", "CONFIRMING", "CAPTURING_DETAILS"}
REPROMPT_AFTER_S = 6
ABANDON_AFTER_S = 20
MAX_CLARIFY_RETRIES = 2
SPICE_WORDS = {"Mild": "mild", "Medium": "medium spicy", "Spicy": "spicy"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def rupees(paise: int) -> int:
    return int(round(paise / 100))


@dataclass
class Line:
    line_id: int
    item_id: int
    name: str
    qty: int
    modifiers: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = "customer"
    upsell_rule_id: Optional[int] = None
    combo_id: Optional[str] = None


@dataclass
class Pending:
    """A question waiting for an answer: which item, or which option of a required group."""
    id: str
    kind: str  # item | group
    options: list[tuple[Any, str]]  # (value, label); value is item_id or option name
    qty: Optional[float] = None
    raw_mods: list[str] = field(default_factory=list)  # "kind:value" to apply once an item is chosen
    line_id: Optional[int] = None
    group: Optional[str] = None
    item_name: Optional[str] = None
    retries: int = 0


@dataclass
class OpenOffer:
    id: str
    offer: Offer
    event_id: Optional[int]
    finalize_after: bool


class CallSession:
    def __init__(self, call_id: str, services, channel: str = "phone"):
        self.call_id = call_id
        self.svc = services
        self.channel = channel
        self.state = "GREETING"
        self.lang = CallLanguage()
        self.lines: list[Line] = []
        self.pending: list[Pending] = []
        self.offer: Optional[OpenOffer] = None
        self.offers_made = 0
        self.offers_accepted = 0
        self.declined_items: set[int] = set()
        self.declined_anchors: set[int] = set()
        self.offered_items: set[int] = set()
        self.applied_combos: dict[str, tuple[list[int], int]] = {}
        self.staff_combos: set[str] = set()  # combos staff added from the menu: not offers
        self.customer_name: Optional[str] = None
        self.customer_phone: Optional[str] = None
        self.awaiting: Optional[str] = None
        self.unknown_streak = 0
        self.reprompted = False
        self.last_category: Optional[str] = None
        self.seq = 0
        self.events: list[dict] = []
        self.transcript: list[dict] = []
        self.order: Optional[dict] = None
        self.outcome: Optional[str] = None
        self.started_at = now_iso()
        self.ended_at: Optional[str] = None
        self._ids = itertools.count(1)
        self._out: list[dict] = []
        self.rng = services.rng_for(call_id)

    # ----- events ---------------------------------------------------------------------

    @property
    def language(self) -> str:
        return self.lang.current or "en"

    def emit(self, type_: str, **payload) -> dict:
        self.seq += 1
        ev = {"type": type_, "seq": self.seq, "ts": now_iso(), **payload}
        self.events.append(ev)
        self._out.append(ev)
        return ev

    def set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.emit("state.changed", state=state)

    def reply(self, text: str, **extra) -> None:
        english = en_of(text)
        # What the voice reads: English for English calls; Devanagari for Hindi and Hinglish calls.
        speech, speech_lang = (str(text), "en") if self.language == "en" else (hi_of(text), "hi")
        self.emit("reply.say", text=str(text), lang=self.language, display_text_en=english,
                  speech_text=speech, speech_lang=speech_lang, **extra)
        self.transcript.append({"t": now_iso(), "speaker": "assistant", "original_text": str(text),
                                "display_text_en": english, "lang": self.language,
                                "text": english})

    def _flush(self) -> list[dict]:
        out, self._out = self._out, []
        self.svc.save_call(self)
        return out

    def error(self, code: str, message: str) -> list[dict]:
        """An error event in the call's sequence (bad client message, PoS trouble)."""
        self.emit("error", code=code, message=message)
        return self._flush()

    def since(self, seq: int) -> list[dict]:
        return [e for e in self.events if e["seq"] > seq]

    # ----- entry points ---------------------------------------------------------------

    def start(self) -> list[dict]:
        if not self.events:
            self.emit("state.changed", state=self.state)
            self.reply(say("greeting", self.lang.current or "hinglish"))
        return self._flush()

    def handle(self, msg: dict) -> list[dict]:
        kind = msg.get("type")
        if self.state not in ACTIVE and kind != "ui.end":
            return []
        self.reprompted = False
        if kind == "transcript.final":
            alts = msg.get("alternatives") if isinstance(msg.get("alternatives"), list) else []
            text = self._best_hypothesis([msg.get("text") or ""] + [a for a in alts[:3] if isinstance(a, str)])
            if text:
                self._on_utterance(text)
        elif kind == "ui.choice":
            self._on_choice(msg.get("clarify_id"), msg.get("option_id"))
        elif kind == "ui.offer":
            if self.offer and msg.get("offer_id") == self.offer.id:
                self._answer_offer(msg.get("action") == "accept")
        elif kind == "ui.add_item":
            self._staff_add(msg.get("item_id"), int(msg.get("qty_delta") or 1))
        elif kind == "ui.barge_in":
            # The caller spoke over the agent; the client has already stopped the voice.
            last = next((ln for ln in reversed(self.transcript) if ln["speaker"] == "assistant"), None)
            if last is not None:
                last["interrupted"] = True
        elif kind == "ui.add_combo":
            self._staff_add_combo(msg.get("combo_id"))
        elif kind == "ui.confirm":
            if self.lines and self.state in ("GREETING", "TAKING_ORDER"):
                self._finalize()
            elif self.state == "CONFIRMING":
                self._start_details()
        elif kind == "ui.send":
            if self.lines and not self.order and not self.pending:
                self.offer = None
                self._place()
        elif kind == "ui.end":
            self._end("ended")
        return self._flush()

    def tick(self, silent_seconds: float) -> list[dict]:
        """Called when the line has been silent for a while."""
        if self.state not in ACTIVE:
            return []
        if silent_seconds >= ABANDON_AFTER_S:
            self.reply(say("abandoned", self.language))
            self._end("abandoned")
        elif silent_seconds >= REPROMPT_AFTER_S and not self.reprompted:
            self.reprompted = True
            self.reply(say("reprompt", self.language))
        return self._flush()

    # ----- utterances -----------------------------------------------------------------

    def _best_hypothesis(self, texts: list[str]) -> str:
        """The open recogniser's transcript comes first; alternatives come from the menu-biased pass.
        An alternative wins only when it matches the menu or an intent clearly better (one more dish,
        or a known intent where the open text has none). Names, phones and addresses keep the open text."""
        def clean(t: str) -> tuple[str, int]:
            words = t.split()
            unk = sum(w == "[unk]" for w in words)
            return " ".join(w for w in words if w != "[unk]").strip(), unk

        cands = [clean(t) for t in texts]
        first = cands[0][0]
        if len(cands) == 1 or self.state == "CAPTURING_DETAILS":
            return first or next((c for c, _ in cands[1:] if c), "")
        cart_ids = {l.item_id for l in self.lines}

        def score(text: str, unk: int) -> float:
            if not text:
                return -10.0
            p = self.svc.parser.parse(text, cart_ids, self.last_category, self.svc.daypart())
            accepted = sum(m.status == "accepted" for m in p.mentions)
            clarify = sum(m.status == "clarify" for m in p.mentions)
            return 2 * accepted + clarify + (1 if p.intent != "unknown" else 0) - 0.5 * unk

        best, best_score = first, score(*cands[0])
        for text, unk in cands[1:]:
            sc = score(text, unk)
            if sc >= best_score + 1:
                best, best_score = text, sc
        return best

    def _on_utterance(self, text: str) -> None:
        cart_ids = {l.item_id for l in self.lines}
        p: Parse = self.svc.parser.parse(text, cart_ids, self.last_category, self.svc.daypart())
        self.lang.update(p.language, len(p.normalized.clean_tokens))
        gloss = gloss_en(p, self.svc.menu)
        original = mask_phones_in_text(text)
        english = mask_phones_in_text(gloss.text)
        parts = [{**pt, "text": mask_phones_in_text(pt["text"])} for pt in gloss.parts]
        self.transcript.append({"t": now_iso(), "speaker": "guest", "original_text": original,
                                "display_text_en": english, "lang": p.language, "parts": parts, "text": english})
        self.emit("transcript", speaker="guest", original_text=original, display_text_en=english,
                  lang=p.language, parts=parts)
        ev = p.to_event()
        ev.pop("type")
        self.emit("nlu.result", **ev)
        for m in p.mentions:
            if m.status == "accepted":
                self.emit("menu.highlight", item_id=m.item_id, kind="heard")

        if self.state == "CLARIFYING" and self._resolve_pending(p):
            return
        if self.state == "OFFERING" and self.offer:
            if p.intent == "confirm":
                self._answer_offer(True)
                return
            if p.intent == "deny":
                self._answer_offer(False)
                return
            self._drop_offer()
        if self.state == "CAPTURING_DETAILS" and self._capture_details(p):
            return
        if self.state == "CONFIRMING":
            if p.intent == "confirm":
                self._start_details()
                return
            if p.intent in ("deny",) and not p.mentions:
                self.set_state("TAKING_ORDER")
                self.reply(say("what_to_change", self.language))
                return
        self._dispatch(p)

    def _dispatch(self, p: Parse) -> None:
        intent = p.intent
        if intent != "unknown":
            self.unknown_streak = 0
        handler = {
            "add_item": self._add_items, "remove_item": self._remove, "modify_item": self._modify,
            "finalize": self._finalize, "ask_price": self._ask_price, "ask_availability": self._ask_availability,
            "ask_recommendation": self._recommend, "repeat_order": self._repeat, "give_name": self._give_name,
            "give_phone": self._give_phone, "give_address": self._give_address, "cancel": self._cancel,
            "greet": self._greet, "confirm": self._confirm_free, "deny": self._deny_free,
        }.get(intent, self._unknown)
        handler(p)

    # ----- cart -----------------------------------------------------------------------

    def _unit_paise(self, line: Line) -> int:
        item = self.svc.menu.items[line.item_id]
        price = item.price_paise
        for group, name in line.modifiers:
            g = item.groups.get(group)
            if g:
                price += g.options.get(name, 0)
        return price

    def _discount_paise(self) -> int:
        ids = {l.item_id for l in self.lines}
        return sum(d for items, d in self.applied_combos.values() if set(items) <= ids)

    def totals(self) -> tuple[int, int, int]:
        sub = sum(self._unit_paise(l) * l.qty for l in self.lines)
        disc = min(self._discount_paise(), sub)
        return sub, disc, sub - disc

    def _label(self, line: Line, with_qty: bool = True) -> str:
        bits = []
        for group, name in line.modifiers:
            if group == "Spice":
                bits.append(SPICE_WORDS.get(name, name.lower()))
            elif group == "Size":
                bits.append(name.lower())
            else:
                bits.append(name.lower())
        bits += line.notes
        extra = f" ({', '.join(bits)})" if bits else ""
        return f"{line.qty} {line.name}{extra}" if with_qty else f"{line.name}{extra}"

    def _cart_event(self) -> None:
        sub, disc, total = self.totals()
        lines = [{
            "line_id": l.line_id, "item_id": l.item_id, "name": l.name, "qty": l.qty,
            "unit_price": rupees(self._unit_paise(l)),
            "modifiers": [{"group": g, "name": n} for g, n in l.modifiers], "notes": l.notes,
            "source": l.source, "upsell_rule_id": l.upsell_rule_id, "combo_id": l.combo_id,
        } for l in self.lines]
        ids = {l.item_id for l in self.lines}
        offer_disc = min(disc, sum(d for cid, (items, d) in self.applied_combos.items()
                                   if cid not in self.staff_combos and set(items) <= ids))
        up_rev = sum(self._unit_paise(l) * l.qty for l in self.lines if l.source in ("upsell", "combo")) - offer_disc
        up_cm = sum((self._unit_paise(l) - self._unit_cost(l)) * l.qty
                    for l in self.lines if l.source in ("upsell", "combo")) - offer_disc
        self.emit("cart.updated", cart={
            "lines": lines, "subtotal": rupees(sub), "discount": rupees(disc), "total": rupees(total),
            "upsell": {"shown": self.offers_made, "accepted": self.offers_accepted,
                       "added_revenue": rupees(up_rev), "added_margin": rupees(up_cm)},
        })

    def _unit_cost(self, line: Line) -> int:
        item = self.svc.menu.items[line.item_id]
        cost = item.food_cost_paise
        for group, name in line.modifiers:
            g = item.groups.get(group)
            if g:
                cost += g.costs.get(name, 0)
        return cost

    def _new_line(self, item_id: int, qty: int, mods: list[tuple[str, str]], notes: list[str],
                  source: str = "customer", rule_id: Optional[int] = None, combo_id: Optional[str] = None) -> Line:
        item = self.svc.menu.items[item_id]
        for l in self.lines:  # same dish, same choices: increase the quantity
            if (l.item_id == item_id and sorted(l.modifiers) == sorted(mods) and sorted(l.notes) == sorted(notes)
                    and l.source == source):
                l.qty += qty
                return l
        line = Line(next(self._ids), item_id, item.name, qty, list(mods), list(notes), source, rule_id, combo_id)
        self.lines.append(line)
        self.last_category = item.category
        return line

    def _apply_mention(self, item_id: int, qty: Optional[float], mods: list[tuple[str, str]], notes: list[str],
                       added: list[Line], problems: list[str], source: str = "customer") -> None:
        item = self.svc.menu.items[item_id]
        if not item.available:
            problems.append(say("unavailable", self.language, item=item.name))
            return
        has_size = "Size" in item.groups
        for n, size in split_fraction(float(qty or 1), has_size):
            m = list(mods)
            if size and has_size:
                m = [x for x in m if x[0] != "Size"] + [("Size", size)]
            line = self._new_line(item_id, n, m, notes, source=source)
            if line not in added:
                added.append(line)
            for gname, g in item.groups.items():
                if g.required and not any(x[0] == gname for x in line.modifiers):
                    if not any(pq.line_id == line.line_id for pq in self.pending):
                        self.pending.append(Pending(
                            id=f"c{next(self._ids)}", kind="group", options=[(o, o) for o in g.options],
                            line_id=line.line_id, group=gname, item_name=item.name))

    def _mods_from_raw(self, item_id: int, raw: list[str], problems: list[str]) -> tuple[list, list]:
        from nlu.modifiers import validate
        mods, notes = [], []
        for r in raw:
            kind, value = r.split(":", 1)
            mod, note, problem = validate(self.svc.menu.items[item_id], kind, value)
            if mod:
                mods.append(mod)
            if note:
                notes.append(note)
            if problem:
                problems.append(problem)
        return mods, notes

    def _add_items(self, p: Parse) -> None:
        added: list[Line] = []
        problems: list[str] = []
        for m in p.mentions:
            problems += m.problems
            if m.status == "accepted":
                self._apply_mention(m.item_id, m.qty, m.modifiers, m.notes, added, problems)
            else:
                raw = [n for n in m.notes if ":" in n]
                self.pending.append(Pending(id=f"c{next(self._ids)}", kind="item",
                                            options=[(c.item_id, c.name) for c in m.candidates[:3]],
                                            qty=m.qty, raw_mods=raw))
        if added:
            self._cart_event()
        self._after_change(added, problems)

    def _after_change(self, added: list[Line], problems: list[str]) -> None:
        parts = [say("modifier_problem", self.language, problem=x) for x in dict.fromkeys(problems)]
        if self.pending:
            self.set_state("CLARIFYING")
            if added:
                parts.append(say("added_short", self.language,
                                 items=join_items([self._label(l) for l in added], self.language)))
            parts.append(self._question(self.pending[0]))
            self.reply(bjoin(parts), clarify_id=self.pending[0].id)
            return
        self.set_state("TAKING_ORDER")
        if added:
            parts.append(say("added", self.language, items=join_items([self._label(l) for l in added], self.language)))
        elif not parts:
            parts.append(say("not_understood_item", self.language))
        self.reply(bjoin(parts))

    # ----- clarification --------------------------------------------------------------

    def _question(self, pq: Pending) -> str:
        labels = [label for _v, label in pq.options]
        text = self._question_text(pq, labels)
        self.emit("clarify.ask", clarify_id=pq.id, kind=pq.kind, question=str(text), question_en=en_of(text),
                  options=[{"id": v, "label": label} for v, label in pq.options])
        return text

    def _staff_add(self, item_id, qty_delta: int) -> None:
        """Staff added or removed an item from the menu panel (source: staff)."""
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return
        item = self.svc.menu.items.get(item_id)
        if item is None:
            return
        self.emit("menu.highlight", item_id=item_id, kind="staff")
        if qty_delta < 0:
            line = next((l for l in reversed(self.lines) if l.item_id == item_id and l.source == "staff"), None)                 or next((l for l in reversed(self.lines) if l.item_id == item_id), None)
            if line is None:
                return
            line.qty += qty_delta
            if line.qty <= 0:
                self.lines.remove(line)
                self.pending = [pq for pq in self.pending if pq.line_id != line.line_id]
            self._cart_event()
            if self.state == "GREETING":
                self.set_state("TAKING_ORDER")
            return
        added: list[Line] = []
        problems: list[str] = []
        self._apply_mention(item_id, qty_delta, [], [], added, problems, source="staff")
        if added:
            self._cart_event()
        if self.pending:
            self._after_change(added, problems)
        elif problems:
            self.reply(bjoin(problems))
        elif self.state in ("GREETING", "OFFERING", "CONFIRMING"):
            self.offer = None
            self.set_state("TAKING_ORDER")

    def _staff_add_combo(self, combo_id) -> None:
        """Staff tapped a combo on the menu: every dish in it goes on the ticket (source: staff, with the
        combo id) and the combo price applies while they are all there. Dishes already on the ticket are not
        added twice. It is not an offer, so it does not count toward offers shown, accepted or added."""
        combo = next((c for c in self.svc.ranker().pool if c.id == combo_id), None)
        if combo is None:
            self.emit("error", code="unknown_combo",
                      message="That combo is no longer offered on calls. Refresh the menu.")
            return
        have = {l.item_id for l in self.lines}
        added: list[Line] = []
        problems: list[str] = []
        for item_id in combo.item_ids:
            if item_id in have or item_id not in self.svc.menu.items:
                continue
            self.emit("menu.highlight", item_id=item_id, kind="staff")
            self._apply_mention(item_id, 1, [], [], added, problems, source="staff")
        for line in added:
            line.combo_id = combo.id
        self.staff_combos.add(combo.id)
        # The saving applies while every dish of the combo is on the ticket (see _discount_paise), so it
        # also covers a dish added after a clarifying question.
        self.applied_combos[combo.id] = (combo.item_ids, combo.list_price_paise - combo.price_paise)
        self._cart_event()
        if self.pending:
            self._after_change(added, problems)
        elif problems:
            self.reply(bjoin(problems))
        elif self.state in ("GREETING", "OFFERING", "CONFIRMING"):
            self.offer = None
            self.set_state("TAKING_ORDER")

    def _question_text(self, pq: Pending, labels: list[str]) -> str:
        opts = join_options(labels, self.language)
        if pq.kind == "group":
            return say("clarify_group", self.language, options=opts, item=pq.item_name)
        if pq.retries:
            return say("clarify_again", self.language, options=opts)
        return say("clarify_item", self.language, options=opts)

    def _resolve_pending(self, p: Parse) -> bool:
        pq = self.pending[0]
        choice = None
        if p.ordinal is not None and -len(pq.options) <= p.ordinal < len(pq.options):
            choice = pq.options[p.ordinal][0]
        elif pq.kind == "group":
            said = [v for _k, v in p.loose_modifiers] + [v for m in p.mentions for g, v in m.modifiers if g == pq.group]
            choice = next((v for v in said if any(v == o for o, _ in pq.options)), None)
            if choice is None:
                text = " ".join(p.normalized.clean_tokens)
                for v, label in pq.options:
                    if label.lower() in text.split():
                        choice = v
        else:
            option_ids = {v for v, _ in pq.options}
            for m in p.mentions:
                ids = [c.item_id for c in m.candidates if c.item_id in option_ids]
                if ids:
                    choice = ids[0]
                    break
            if choice is None:
                labels = {v: label.lower() for v, label in pq.options}
                tokens = set(p.normalized.clean_tokens)
                hits = [v for v, label in labels.items()
                        if tokens & (set(label.split()) - set.intersection(*[set(l.split()) for l in labels.values()]))]
                if len(hits) == 1:
                    choice = hits[0]
        if choice is not None:
            self._choose(pq, choice)
            return True
        if p.mentions or p.intent in ("finalize", "cancel", "remove_item", "repeat_order"):
            self.pending.pop(0)  # the guest moved on; drop the question
            self.set_state("TAKING_ORDER")
            return False
        pq.retries += 1
        if pq.retries > MAX_CLARIFY_RETRIES:
            self.pending.pop(0)
            self._after_change([], [])
            return True
        self.reply(self._question(pq), clarify_id=pq.id)
        return True

    def _on_choice(self, clarify_id: Optional[str], option_id) -> None:
        if not self.pending or self.pending[0].id != clarify_id:
            return
        pq = self.pending[0]
        for v, _label in pq.options:
            if str(v) == str(option_id):
                self._choose(pq, v)
                return

    def _choose(self, pq: Pending, value) -> None:
        self.pending.pop(0)
        added: list[Line] = []
        problems: list[str] = []
        if pq.kind == "item":
            mods, notes = self._mods_from_raw(value, pq.raw_mods, problems)
            self._apply_mention(value, pq.qty, mods, notes, added, problems)
        else:
            line = next((l for l in self.lines if l.line_id == pq.line_id), None)
            if line:
                line.modifiers = [m for m in line.modifiers if m[0] != pq.group] + [(pq.group, value)]
                added.append(line)
        self._cart_event()
        self._after_change(added, problems)

    # ----- remove / modify ------------------------------------------------------------

    def _target_line(self, p: Parse) -> Optional[Line]:
        for m in p.mentions:
            ids = [m.item_id] if m.status == "accepted" else [c.item_id for c in m.candidates]
            for l in reversed(self.lines):
                if l.item_id in ids:
                    return l
        return self.lines[-1] if self.lines else None

    def _remove(self, p: Parse) -> None:
        line = self._target_line(p)
        if line is None:
            self.reply(say("nothing_to_remove", self.language))
            return
        qty = next((m.qty for m in p.mentions if m.qty), None)
        if qty and qty < line.qty:
            line.qty -= int(qty)
        else:
            self.lines.remove(line)
            self.pending = [pq for pq in self.pending if pq.line_id != line.line_id]
        self._cart_event()
        self.set_state("TAKING_ORDER")
        self.reply(say("removed", self.language, item=line.name))

    def _modify(self, p: Parse) -> None:
        from nlu.modifiers import validate
        line = self._target_line(p)
        if line is None:
            self.reply(say("nothing_to_remove", self.language))
            return
        mods = list(p.loose_modifiers)
        for m in p.mentions:
            mods += [(k.lower() if k != "Add-ons" else "addon", v) for k, v in m.modifiers]
            mods += [("exclusion", n.removeprefix("no ")) for n in m.notes if n.startswith("no ")]
        changes, problems = [], []
        item = self.svc.menu.items[line.item_id]
        for kind, value in mods:
            kind = {"size": "size", "spice": "spice", "addon": "addon", "exclusion": "exclusion",
                    "add-ons": "addon"}.get(kind, kind)
            mod, note, problem = validate(item, kind, value)
            if mod:
                keep_others = mod[0] == "Add-ons"
                line.modifiers = [x for x in line.modifiers if keep_others or x[0] != mod[0]] + [mod]
                changes.append(SPICE_WORDS.get(mod[1], mod[1].lower()) if mod[0] == "Spice" else mod[1].lower())
            if note and note not in line.notes:
                line.notes.append(note)
                changes.append(note)
            if problem:
                problems.append(problem)
        self._cart_event()
        self.set_state("TAKING_ORDER")
        if changes:
            text = say("modified", self.language, item=line.name, change=", ".join(changes))
            if problems:
                text = bjoin([*problems, text])
            self.reply(text)
        else:
            self.reply(bjoin(problems) if problems else say("unknown", self.language))

    # ----- offers ---------------------------------------------------------------------

    def _try_offer(self, finalize_after: bool) -> bool:
        conf = self.svc.settings()
        up = conf["upsell"]
        if not up.get("enabled", True) or not self.lines or self.pending:
            return False
        ctx = UpsellContext(
            cart_item_ids=[l.item_id for l in self.lines], daypart=self.svc.daypart(),
            declined_item_ids=self.declined_items, declined_anchor_ids=self.declined_anchors,
            offered_item_ids=self.offered_items, offers_made=self.offers_made,
            max_offers=int(up.get("max_offers_per_call", 2)),
            daypart_weight=float(up.get("daypart_weights", {}).get(self.svc.daypart(), 1.0)), rng=self.rng,
        )
        ranked = self.svc.ranker().rank(ctx)
        if not ranked:
            return False
        offer = ranked[0]
        oid = f"o{self.offers_made + 1}"
        self.offers_made += 1
        self.offered_items.add(offer.item_id)
        event_id = self.svc.record_offer(self.call_id, offer)
        self.offer = OpenOffer(oid, offer, event_id, finalize_after)
        self.set_state("OFFERING")
        self.emit("upsell.offer", offer_id=oid, kind=offer.kind,
                  item={"id": offer.item_id, "name": offer.name, "price": rupees(offer.price_paise)},
                  reason=offer.reason)
        if offer.kind == "combo":
            combo = next((c for c in self.svc.ranker().pool if c.id == offer.combo_id), None)
            text = say("offer_combo", self.language, item=offer.name,
                       combo=" + ".join(combo.names) if combo else offer.name,
                       total=rupees(combo.price_paise) if combo else rupees(offer.price_paise))
        else:
            text = say("offer", self.language, item=offer.name, price=rupees(offer.price_paise))
        self.reply(text, offer_id=oid)
        return True

    def _answer_offer(self, accepted: bool) -> None:
        o = self.offer
        self.offer = None
        offer = o.offer
        if offer.rule_id:
            self.svc.learn(offer.rule_id, accepted)
        self.svc.record_offer_result(o.event_id, accepted)
        parts = []
        if accepted:
            self.offers_accepted += 1
            source = "combo" if offer.kind == "combo" else "upsell"
            item = self.svc.menu.items[offer.item_id]
            standard = [(g, next(iter(grp.options))) for g, grp in item.groups.items() if grp.required and grp.options]
            self._new_line(offer.item_id, 1, standard, [], source=source, rule_id=offer.rule_id,
                           combo_id=offer.combo_id)
            if offer.kind == "combo" and offer.combo_id:
                combo = next((c for c in self.svc.ranker().pool if c.id == offer.combo_id), None)
                if combo:
                    self.applied_combos[combo.id] = (combo.item_ids, offer.combo_discount_paise)
            self._cart_event()
            parts.append(say("offer_accepted", self.language, item=offer.name))
        else:
            self.declined_items.add(offer.item_id)
            if offer.anchor_item_id:
                self.declined_anchors.add(offer.anchor_item_id)
            self._cart_event()
            parts.append(say("offer_declined", self.language))
        if o.finalize_after:
            self._readback(prefix=bjoin(parts))
        else:
            self.set_state("TAKING_ORDER")
            self.reply(bjoin(parts))

    def _drop_offer(self) -> None:
        if self.offer:
            self.svc.record_offer_result(self.offer.event_id, None)
            self.offer = None
            self.set_state("TAKING_ORDER")

    # ----- finalize -------------------------------------------------------------------

    def _finalize(self, p: Parse | None = None) -> None:
        if not self.lines:
            self.set_state("TAKING_ORDER")
            self.reply(say("empty_cart", self.language))
            return
        if self._try_offer(finalize_after=True):
            return
        self._readback()

    def _readback(self, prefix: str = "") -> None:
        sub, disc, total = self.totals()
        text = say("readback", self.language, items=join_items([self._label(l) for l in self.lines], self.language),
                   total=rupees(total))
        self.set_state("CONFIRMING")
        self.reply(bjoin([prefix, text]))

    def _start_details(self) -> None:
        self.set_state("CAPTURING_DETAILS")
        self._next_detail()

    def _next_detail(self) -> None:
        if not self.customer_name:
            self.awaiting = "name"
            self.reply(say("ask_name", self.language))
        elif not self.customer_phone:
            self.awaiting = "phone"
            self.reply(say("ask_phone", self.language))
        else:
            self.awaiting = None
            self._place()

    def _capture_details(self, p: Parse) -> bool:
        if p.intent in ("add_item", "remove_item", "modify_item", "cancel", "repeat_order") and (p.mentions or p.intent != "add_item"):
            return False
        from nlu import intent as intent_mod
        from nlu.parser import STOPWORDS
        phone = p.phone or intent_mod.extract_phone(p.normalized.tokens)
        if phone:
            self._set_phone(phone)
        if self.awaiting == "name":
            name = p.name or intent_mod.extract_name(p.normalized.text)
            if not name and not phone:
                words = [w for w in p.normalized.clean_tokens if w.isalpha() and w not in STOPWORDS]
                if 1 <= len(words) <= 3:
                    name = " ".join(w.capitalize() for w in words[:2])
            if name:
                self.customer_name = name
        elif self.awaiting == "phone" and not phone:
            self.reply(say("phone_invalid", self.language))
            return True
        if self.awaiting == "phone" and phone and not self._phone_ok(phone):
            self.customer_phone = None
            self.reply(say("phone_invalid", self.language))
            return True
        self._next_detail()
        return True

    @staticmethod
    def _phone_ok(phone: str) -> bool:
        return len(phone) == 10 and phone[0] in "6789"

    def _set_phone(self, phone: str) -> None:
        if self._phone_ok(phone):
            self.customer_phone = phone

    def _place(self) -> None:
        draft = DraftOrder(
            call_id=self.call_id, channel=self.channel,
            language=self.language if self.language in ("en", "hi", "hinglish", "mr", "gu") else "en",
            customer_name=self.customer_name, customer_phone=self.customer_phone,
            lines=[DraftLine(item_id=l.item_id, qty=l.qty,
                             modifiers=[DraftModifier(group=g, name=n) for g, n in l.modifiers],
                             notes=", ".join(l.notes), source=l.source,
                             upsell_rule_id=l.upsell_rule_id if l.source == "upsell" else None)
                   for l in self.lines],
            upsell_shown=self.offers_made, discount=rupees(self._discount_paise()),
        )
        try:
            payload, result = self.svc.place(draft)
        except OrderRejected as exc:
            self.set_state("CONFIRMING")
            self.reply(say("order_error", self.language, reason=exc.message))
            return
        self.order = payload.to_json_dict()
        self.emit("order.finalized", order=self.order)
        for ev in result.events:
            ev = dict(ev)
            t = ev.pop("type")
            self.emit(t, **ev)
        self.set_state("FINALIZED")
        if result.status == "acked":
            self.reply(say("placed", self.language, kot=result.kot_no))
        else:
            self.reply(say("pos_problem", self.language))
        self.outcome = "ordered"
        self.ended_at = now_iso()

    # ----- other intents --------------------------------------------------------------

    def _ask_price(self, p: Parse) -> None:
        m = next((m for m in p.mentions if m.status == "accepted"), None)
        if m:
            item = self.svc.menu.items[m.item_id]
            self.reply(say("price", self.language, item=item.name, price=rupees(item.price_paise)))
        elif p.mentions:
            self._add_items(p)
        else:
            self.reply(say("total", self.language, total=rupees(self.totals()[2])))

    def _ask_availability(self, p: Parse) -> None:
        m = next((m for m in p.mentions if m.status == "accepted"), None)
        if not m:
            self._unknown(p)
            return
        item = self.svc.menu.items[m.item_id]
        self.reply(say("available" if item.available else "unavailable", self.language, item=item.name))

    def _recommend(self, p: Parse) -> None:
        if self.lines and self._try_offer(finalize_after=False):
            return
        pick = self.svc.recommendation(exclude={l.item_id for l in self.lines})
        if pick is None:
            self._unknown(p)
            return
        self.reply(say("recommend", self.language, item=pick.name, price=rupees(pick.price_paise)))

    def _repeat(self, p: Parse) -> None:
        if not self.lines:
            self.reply(say("empty_cart", self.language))
            return
        self.reply(say("repeat", self.language, items=join_items([self._label(l) for l in self.lines], self.language),
                       total=rupees(self.totals()[2])))

    def _give_name(self, p: Parse) -> None:
        if p.name:
            self.customer_name = p.name
        self.reply(say("thanks_name", self.language, name=self.customer_name or ""))

    def _give_phone(self, p: Parse) -> None:
        if p.phone:
            self._set_phone(p.phone)
        self.reply(say("noted_phone", self.language) if self.customer_phone else say("phone_invalid", self.language))

    def _give_address(self, p: Parse) -> None:
        self.reply(say("greet_back", self.language))

    def _cancel(self, p: Parse) -> None:
        self.reply(say("cancelled", self.language))
        self._end("cancelled")

    def _greet(self, p: Parse) -> None:
        self.set_state("TAKING_ORDER" if self.state == "GREETING" else self.state)
        self.reply(say("greet_back", self.language))

    def _confirm_free(self, p: Parse) -> None:
        if self.state == "CONFIRMING":
            self._start_details()
        else:
            self.reply(say("greet_back", self.language))

    def _deny_free(self, p: Parse) -> None:
        # "Anything else?" -> "No": the guest is done.
        if self.lines:
            self._finalize(p)
        else:
            self.reply(say("greet_back", self.language))

    def _unknown(self, p: Parse) -> None:
        self.unknown_streak += 1
        if self.unknown_streak >= 2:
            self.reply(say("unknown_typed", self.language), suggest_typed=True)
        else:
            self.reply(say("unknown", self.language))

    def _end(self, outcome: str) -> None:
        if self.state in ACTIVE:
            self.outcome = outcome
            self.ended_at = now_iso()
            self.set_state("ABANDONED")

    # ----- snapshot ---------------------------------------------------------------------

    def snapshot(self) -> dict:
        sub, disc, total = self.totals()
        return {
            "call_id": self.call_id, "state": self.state, "language": self.language,
            "customer": {"name": self.customer_name, "phone": mask_phone(self.customer_phone)},
            "lines": [{"item_id": l.item_id, "name": l.name, "qty": l.qty,
                       "modifiers": [{"group": g, "name": n} for g, n in l.modifiers], "notes": l.notes,
                       "source": l.source} for l in self.lines],
            "subtotal": rupees(sub), "discount": rupees(disc), "total": rupees(total),
            "offers": {"shown": self.offers_made, "accepted": self.offers_accepted},
            "order": self.order, "outcome": self.outcome, "seq": self.seq,
        }
