"""Score a chat result against one evaluation case."""

from __future__ import annotations

import re


def missing_terms(answer: str, terms: list[str]) -> list[str]:
    folded = answer.casefold()
    return [term for term in terms if term.casefold() not in folded]


def _cites(citations: list[str], doc_id: str) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(doc_id)}(?![A-Za-z0-9])")
    return any(pattern.search(label) for label in citations)


def evaluate_case(result: dict, case: dict, *, check_intent: bool = True) -> dict:
    answer = result.get("answer") or ""
    missing = missing_terms(answer, case["must_include"])
    forbidden = [term for term in case["forbid"] if term.casefold() in answer.casefold()]
    citations = list(result.get("citations") or [])
    missing_docs = [doc for doc in case["expect_docs"] if not _cites(citations, doc)]
    unexpected_citations = bool(citations) and not case["expect_docs"]
    intent_ok = (not check_intent) or result.get("intent") == case["expected_intent"]
    ok = intent_ok and not missing and not forbidden and not missing_docs and not unexpected_citations
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_intent": case["expected_intent"],
        "intent": result.get("intent"),
        "intent_ok": intent_ok,
        "answer": answer,
        "citations": list(result.get("citations") or []),
        "missing": missing,
        "forbidden": forbidden,
        "missing_docs": missing_docs,
        "unexpected_citations": unexpected_citations,
        "latency_ms": result.get("latency_ms"),
        "ok": ok,
    }
