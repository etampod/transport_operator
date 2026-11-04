"""Tools whose job is not retrieval.

The tariff and the compensation bands live in the policy text. These tools
read that text and apply it to numbers in the question. The resulting amount
is not stored as a sentence in the corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache

from podoba_helpdesk.corpus import load_corpus
from podoba_helpdesk.textutil import apply_synonyms, normalize_ws, split_sentences, zone_count

_CENTS = Decimal("0.01")
_ADULT_SECTION = "Adult single tickets"
_CHILD_SECTION = "Child fares"
_THRESHOLD_SECTION = "Compensation thresholds"
_STRIKE_SECTION = "Announced strikes"

_ZONE1 = re.compile(r"(\d+(?:\.\d+)?)\s+EUR in zone 1", re.IGNORECASE)
_EXTRA_ZONE = re.compile(r"additional zone adds\s+(\d+(?:\.\d+)?)\s+EUR", re.IGNORECASE)
_HALF = re.compile(r"\bhalf the adult\b", re.IGNORECASE)
_UNDER = re.compile(r"under\s+(\d+)\s+minutes", re.IGNORECASE)
_PARTIAL = re.compile(
    r"(\d+)\s+to\s+(\d+)\s+minutes qualifies for compensation of\s+(\d+)\s+percent",
    re.IGNORECASE,
)
_FULL = re.compile(
    r"(\d+)\s+minutes or more qualifies for compensation of\s+(\d+)\s+percent",
    re.IGNORECASE,
)
_STRIKE_HOURS = re.compile(r"at least\s+(\d+)\s+hours", re.IGNORECASE)
_NOTICE_HOURS = re.compile(r"\b(\d+)\s+hours?\b", re.IGNORECASE)
_CHILD = re.compile(r"\b(child|children)\b", re.IGNORECASE)
_PRICE = re.compile(r"\b(\d+(?:\.\d{1,2})?)\s*eur\b", re.IGNORECASE)
_PRICE_EUR_FIRST = re.compile(r"\beur\s*(\d+(?:\.\d{1,2})?)\b", re.IGNORECASE)
_PRICE_WORD = re.compile(
    r"\b(?:cost|costs|price|priced)\s+(?:of\s+)?(\d+(?:\.\d{1,2})?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FareSchedule:
    zone1: Decimal
    extra_zone: Decimal
    adult_rule: str
    child_rule: str


@dataclass(frozen=True)
class DelaySchedule:
    free_under_minutes: int
    partial_until_minutes: int
    partial_percent: int
    full_percent: int
    strike_notice_hours: int
    below_rule: str
    partial_rule: str
    full_rule: str
    strike_rule: str


def money(amount: Decimal) -> str:
    quantized = amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
    return f"{quantized:.2f}"


def _zone_word(zones: int) -> str:
    return "zone" if zones == 1 else "zones"


def _section_text(doc_id: str, section: str) -> str:
    for chunk in load_corpus().chunks:
        if chunk.doc_id == doc_id and chunk.section == section:
            return chunk.text
    raise ValueError(f"Policy section {doc_id} / {section} is missing.")


def _sentence(text: str, pattern: re.Pattern[str]) -> str:
    for sentence in split_sentences(text):
        if pattern.search(sentence):
            return sentence
    raise ValueError(f"No policy sentence matches {pattern.pattern!r}.")


@lru_cache(maxsize=1)
def fare_schedule() -> FareSchedule:
    adult = _section_text("POL-FARE", _ADULT_SECTION)
    child = _section_text("POL-FARE", _CHILD_SECTION)
    zone1 = _ZONE1.search(adult)
    extra = _EXTRA_ZONE.search(adult)
    if zone1 is None or extra is None or _HALF.search(child) is None:
        raise ValueError("POL-FARE does not state the zone tariff and the child half-fare.")
    return FareSchedule(
        zone1=Decimal(zone1.group(1)),
        extra_zone=Decimal(extra.group(1)),
        adult_rule=adult,
        child_rule=_sentence(child, _HALF),
    )


@lru_cache(maxsize=1)
def delay_schedule() -> DelaySchedule:
    thresholds = _section_text("POL-DELAY", _THRESHOLD_SECTION)
    strike = _section_text("POL-DELAY", _STRIKE_SECTION)
    under = _UNDER.search(thresholds)
    partial = _PARTIAL.search(thresholds)
    full = _FULL.search(thresholds)
    notice = _STRIKE_HOURS.search(strike)
    if under is None or partial is None or full is None or notice is None:
        raise ValueError("POL-DELAY does not state the compensation bands and the strike notice.")
    free_under = int(under.group(1))
    partial_from = int(partial.group(1))
    partial_to = int(partial.group(2))
    full_from = int(full.group(1))
    if partial_from != free_under or full_from != partial_to + 1:
        raise ValueError("POL-DELAY compensation bands do not meet.")
    return DelaySchedule(
        free_under_minutes=free_under,
        partial_until_minutes=full_from,
        partial_percent=int(partial.group(3)),
        full_percent=int(full.group(2)),
        strike_notice_hours=int(notice.group(1)),
        below_rule=_sentence(thresholds, _UNDER),
        partial_rule=_sentence(thresholds, _PARTIAL),
        full_rule=_sentence(thresholds, _FULL),
        strike_rule=_sentence(strike, _STRIKE_HOURS),
    )


def _parse_price(text: str) -> Decimal | None:
    folded = text.casefold().replace("€", " eur ")
    match = _PRICE.search(folded) or _PRICE_EUR_FIRST.search(folded) or _PRICE_WORD.search(folded)
    if match is None:
        return None
    return Decimal(match.group(1))


def _percent_of(price: Decimal, percent: int) -> Decimal:
    return (price * Decimal(percent) / Decimal(100)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def _prepared(query: str) -> str:
    return apply_synonyms(normalize_ws(query)).casefold()


def calculate_fare(query: str) -> dict:
    folded = _prepared(query)
    zones = zone_count(folded)
    if zones is None:
        return {
            "answer": "I need the number of zones to calculate a single ticket price.",
            "citations": ["POL-FARE — Adult single tickets"],
        }
    schedule = fare_schedule()
    adult = schedule.zone1 + schedule.extra_zone * (zones - 1)
    if _CHILD.search(folded):
        price = (adult / Decimal(2)).quantize(_CENTS, rounding=ROUND_HALF_UP)
        answer = (
            f"A child single ticket for {zones} {_zone_word(zones)} costs {money(price)} EUR. "
            f"{schedule.child_rule} "
            f"The adult single fare for {zones} {_zone_word(zones)} is {money(adult)} EUR."
        )
        citations = ["POL-FARE — Adult single tickets", "POL-FARE — Child fares"]
    else:
        answer = (
            f"An adult single ticket for {zones} {_zone_word(zones)} costs {money(adult)} EUR. "
            f"{schedule.adult_rule}"
        )
        citations = ["POL-FARE — Adult single tickets"]
    return {"answer": answer, "citations": citations}


def _announced_strike(text: str, minimum_hours: int) -> bool:
    if "strike" not in text or "announced" not in text:
        return False
    notice = [int(value) for value in _NOTICE_HOURS.findall(text)]
    return any(hours >= minimum_hours for hours in notice)


def assess_delay_compensation(query: str) -> dict:
    folded = _prepared(query)
    schedule = delay_schedule()
    minute_match = re.search(r"\b(\d+)\s+minutes?\b", folded)
    price = _parse_price(folded)
    if minute_match is None or price is None:
        return {
            "answer": (
                "I need the delay in minutes and the single ticket price in EUR "
                "to calculate compensation."
            ),
            "citations": ["POL-DELAY — Compensation thresholds"],
        }
    minutes = int(minute_match.group(1))
    if _announced_strike(folded, schedule.strike_notice_hours):
        return {
            "answer": (
                f"{schedule.strike_rule} "
                f"The compensation amount is 0.00 EUR. The delay used is {minutes} minutes."
            ),
            "citations": ["POL-DELAY — Announced strikes"],
        }
    if minutes < schedule.free_under_minutes:
        return {
            "answer": (
                "The delay does not qualify for compensation. "
                f"{schedule.below_rule} "
                f"The compensation amount is 0.00 EUR. The ticket price used is {money(price)} EUR "
                f"and the delay used is {minutes} minutes."
            ),
            "citations": ["POL-DELAY — Compensation thresholds"],
        }
    if minutes < schedule.partial_until_minutes:
        amount = _percent_of(price, schedule.partial_percent)
        rule = schedule.partial_rule
    else:
        amount = _percent_of(price, schedule.full_percent)
        rule = schedule.full_rule
    return {
        "answer": (
            f"The compensation is {money(amount)} EUR. {rule} "
            f"The ticket price used is {money(price)} EUR and the delay used is {minutes} minutes."
        ),
        "citations": ["POL-DELAY — Compensation thresholds"],
    }


TOOL_RUNNERS = {
    "calculate_fare": calculate_fare,
    "assess_delay_compensation": assess_delay_compensation,
}
