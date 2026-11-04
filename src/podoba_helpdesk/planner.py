"""Intent classification and subtask decomposition.

Routing is deterministic. A customer-service desk should not let a small
generative model decide whether a question is in scope or which tool runs.
Each subtask carries only its own text.
"""

from __future__ import annotations

import re

from podoba_helpdesk.textutil import states_ticket_price, zone_count

_CHITCHAT = re.compile(
    r"^(hi|hello|hey|good morning|good afternoon|good evening|thanks|thank you|"
    r"who are you|what can you do)\b"
)

_SPLIT = re.compile(
    r"\s*,\s*and\s+|\s+and\s+(?=how\b|what\b|when\b|who\b|where\b|which\b)",
    re.IGNORECASE,
)

_DOMAIN = re.compile(
    r"\b("
    r"tickets?|fares?|zones?|refunds?|refunded|compensation|delays?|delayed|"
    r"complaints?|wheelchairs?|bicycles?|bikes?|penalty|ombudsman|luggage|"
    r"assistance|prm|ito|podoba|intercom"
    r")\b",
    re.IGNORECASE,
)

_DOMAIN_PHRASES = (
    "lost property",
    "senior card",
    "day cap",
    "city centre",
    "off-peak",
    "working days",
    "photo identification",
    "priority seat",
)


def has_domain(text: str) -> bool:
    folded = " ".join((text or "").split()).casefold()
    if any(phrase in folded for phrase in _DOMAIN_PHRASES):
        return True
    return _DOMAIN.search(folded) is not None


def split_parts(query: str) -> list[str]:
    text = " ".join((query or "").split()).strip()
    if text.count("?") >= 2:
        parts = [part.strip(" .") for part in text.split("?") if part.strip(" .")]
        if len(parts) >= 2:
            return parts
    pieces = [part.strip(" ?.") for part in _SPLIT.split(text) if part.strip(" ?.")]
    if len(pieces) >= 2:
        return pieces
    return [text]


def is_delay_case(text: str) -> bool:
    folded = text.casefold()
    has_minutes = re.search(r"\b\d+\s+minutes?\b", folded) is not None
    has_delay = re.search(r"\b(late|delay|delayed)\b", folded) is not None
    return has_minutes and has_delay and states_ticket_price(folded)


def is_fare_calc(text: str) -> bool:
    if zone_count(text) is None:
        return False
    folded = text.casefold()
    return re.search(r"\b(how much|cost|costs|price|fare|pay)\b", folded) is not None


def is_multi(text: str) -> bool:
    parts = split_parts(text)
    if len(parts) < 2:
        return False
    return all(has_domain(part) or is_delay_case(part) or is_fare_calc(part) for part in parts)


def classify(query: str, *, allow_multi: bool = True) -> str:
    folded = " ".join((query or "").split()).casefold()
    if not folded:
        return "out_of_scope"
    if _CHITCHAT.search(folded) and not has_domain(folded):
        return "chitchat"
    if allow_multi and is_multi(folded):
        return "multi_part"
    if is_delay_case(folded):
        return "delay_compensation"
    if is_fare_calc(folded):
        return "fare_calc"
    if has_domain(folded):
        return "policy_lookup"
    return "out_of_scope"


def _task(task_id: int, kind: str, query: str, tool: str | None) -> dict:
    return {
        "id": task_id,
        "kind": kind,
        "query": query.strip(),
        "tool": tool,
        "status": "pending",
    }


def build_subtasks(query: str, intent: str) -> list[dict]:
    if intent in {"chitchat", "out_of_scope"}:
        return []
    if intent == "fare_calc":
        return [_task(1, "tool", query, "calculate_fare")]
    if intent == "delay_compensation":
        return [_task(1, "tool", query, "assess_delay_compensation")]
    if intent == "multi_part":
        tasks = []
        for index, part in enumerate(split_parts(query), start=1):
            part_intent = classify(part, allow_multi=False)
            if part_intent == "fare_calc":
                tasks.append(_task(index, "tool", part, "calculate_fare"))
            elif part_intent == "delay_compensation":
                tasks.append(_task(index, "tool", part, "assess_delay_compensation"))
            else:
                tasks.append(_task(index, "rag", part, None))
        return tasks
    return [_task(1, "rag", query, None)]
