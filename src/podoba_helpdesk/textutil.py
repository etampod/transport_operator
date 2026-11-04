"""Token helpers shared by routing, retrieval, and the extractive model."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "am",
        "do",
        "does",
        "did",
        "of",
        "to",
        "for",
        "and",
        "or",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "into",
        "that",
        "this",
        "it",
        "its",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "they",
        "what",
        "when",
        "where",
        "who",
        "which",
        "why",
        "how",
        "can",
        "could",
        "please",
        "there",
        "much",
        "many",
        "long",
    }
)

# Surface forms that should share a retrieval token. Applied on both sides.
TOKEN_MAP = {
    "tickets": "ticket",
    "fares": "fare",
    "zones": "zone",
    "costs": "cost",
    "delays": "delay",
    "delayed": "delay",
    "complaints": "complaint",
    "bicycles": "bicycle",
    "bikes": "bicycle",
    "bike": "bicycle",
    "refunds": "refund",
    "minutes": "minute",
    "hours": "hour",
    "days": "day",
    "trains": "train",
    "passengers": "passenger",
    "validity": "valid",
    "buy": "purchase",
    "bought": "purchase",
}

# Whole-word rewrites applied before intent classification.
SYNONYMS = {
    "bike": "bicycle",
    "bikes": "bicycles",
    "kid": "child",
    "kids": "child",
    "reimburse": "refund",
    "reimbursed": "refund",
    "reimbursement": "refund",
}

_WORD = re.compile(r"[A-Za-z]+")
_TOKEN = re.compile(r"[a-z0-9]+")


def normalize_ws(text: str) -> str:
    return " ".join((text or "").split()).strip()


def apply_synonyms(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        mapped = SYNONYMS.get(word.casefold())
        return mapped if mapped else word

    return _WORD.sub(repl, text)


def content_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN.findall((text or "").casefold()):
        if raw in STOPWORDS:
            continue
        mapped = TOKEN_MAP.get(raw, raw)
        if mapped in STOPWORDS:
            continue
        tokens.append(mapped)
    return tokens


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [part.strip() for part in parts if part.strip()]


def is_definition_query(text: str) -> bool:
    folded = (text or "").casefold()
    markers = ("stand for", "what does", "short for", "abbreviation", "meaning of")
    return any(marker in folded for marker in markers)


def overlap_count(query_tokens: list[str], text: str) -> int:
    if not query_tokens:
        return 0
    vocabulary = set(content_tokens(text))
    return sum(1 for token in set(query_tokens) if token in vocabulary)


# "3 zones" or "for zone 3". "in zone 1" is the published base fare, not a formula.
_ZONE_COUNT = re.compile(
    r"\b([1-9]\d*)\s+zones?\b|\bfor zone\s+([1-9]\d*)\b",
    re.IGNORECASE,
)
_TICKET_PRICE = re.compile(
    r"\b\d+(?:\.\d{1,2})?\s*(?:eur|€)\b"
    r"|\b(?:eur|€)\s*\d+(?:\.\d{1,2})?\b"
    r"|\b(?:cost|costs|priced|price)\s+(?:of\s+)?\d+(?:\.\d{1,2})?\b",
    re.IGNORECASE,
)


def zone_count(text: str) -> int | None:
    match = _ZONE_COUNT.search(text or "")
    if match is None:
        return None
    raw = match.group(1) or match.group(2)
    return int(raw)


def states_ticket_price(text: str) -> bool:
    """True when the question states an amount, not merely the word "price"."""
    normalized = (text or "").replace("€", " EUR ")
    return _TICKET_PRICE.search(normalized) is not None
