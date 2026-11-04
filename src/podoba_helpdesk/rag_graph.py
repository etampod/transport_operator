"""RAG subgraph.

These nodes are a compiled graph of their own. The parent calls the compiled
graph as one step. They are not nodes of the parent workflow.

Flow: prepare_query -> retrieve -> grade_documents. A weak grade may broaden
the query once, by appending the policy section titles, and retrieve again.
draft_answer then copies a grounded sentence.
Coverage is always measured against the passenger's original question, so
abbreviation expansion cannot dilute it.
"""

from __future__ import annotations

import operator
import re
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from podoba_helpdesk.config import NOT_FOUND_ANSWER
from podoba_helpdesk.llm import LLM
from podoba_helpdesk.retriever import BM25Retriever
from podoba_helpdesk.textutil import content_tokens, is_definition_query

# Below this lexical coverage the passage is not an answer, and the first
# pass may broaden the query once.
WEAK_COVERAGE = 0.2

_ABBREVIATIONS = (
    ("prm", "passenger with reduced mobility"),
    ("ito", "independent travel ombudsman"),
)


class RagState(TypedDict, total=False):
    query: str
    prepared_query: str
    hits: list[dict]
    passages: list[dict]
    answer: str
    citations: list[str]
    retries: int
    trace: Annotated[list[dict], operator.add]


def _trace(node: str, detail: str, started: float) -> dict:
    return {
        "node": node,
        "detail": detail,
        "ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _coverage(query: str, text: str) -> float:
    query_tokens = set(content_tokens(query))
    if not query_tokens:
        return 0.0
    text_tokens = set(content_tokens(text))
    return len(query_tokens & text_tokens) / len(query_tokens)


def _grade(query: str, hits: list[dict]) -> list[dict]:
    if not hits:
        return []
    definition = is_definition_query(query)
    peak = max((float(hit.get("bm25") or 0) for hit in hits), default=0.0) or 1.0
    graded: list[dict] = []
    for hit in hits:
        coverage = _coverage(query, hit["text"])
        score = 0.35 * (float(hit.get("bm25") or 0) / peak) + 0.65 * coverage
        if hit["doc_id"] == "POL-GLO" and not definition:
            score *= 0.05
        if hit["doc_id"] == "POL-GLO" and definition:
            score += 0.5
        graded.append(
            {
                **hit,
                "coverage": round(coverage, 4),
                "score": round(score, 4),
            }
        )
    graded.sort(key=lambda item: item["score"], reverse=True)
    return [item for item in graded if item["coverage"] >= WEAK_COVERAGE][:3]


def _expand_abbreviations(query: str) -> str:
    folded = query.casefold()
    extras: list[str] = []
    for short, expansion in _ABBREVIATIONS:
        if re.search(rf"\b{re.escape(short)}\b", folded) and expansion not in folded:
            extras.append(expansion)
    if not extras:
        return query
    return f"{query} {' '.join(extras)}"


def build_rag_subgraph(retriever: BM25Retriever, llm: LLM):
    def prepare_query(state: RagState) -> dict:
        started = time.perf_counter()
        query = state.get("query") or ""
        prepared = _expand_abbreviations(query)
        return {
            "prepared_query": prepared,
            "retries": int(state.get("retries") or 0),
            "trace": [_trace("prepare_query", prepared, started)],
        }

    def retrieve(state: RagState) -> dict:
        started = time.perf_counter()
        prepared = state.get("prepared_query") or state.get("query") or ""
        hits = retriever.search(prepared, k=6)
        detail = ", ".join(hit["doc_id"] for hit in hits[:3]) or "no hits"
        return {
            "hits": hits,
            "trace": [_trace("retrieve", detail, started)],
        }

    def grade_documents(state: RagState) -> dict:
        started = time.perf_counter()
        question = state.get("query") or ""
        passages = _grade(question, list(state.get("hits") or []))
        if passages:
            best = passages[0]
            detail = f"{best['citation']} coverage {best['coverage']:.2f}"
        else:
            detail = "no passage kept"
        return {
            "passages": passages,
            "trace": [_trace("grade_documents", detail, started)],
        }

    def broaden_query(state: RagState) -> dict:
        started = time.perf_counter()
        prepared = state.get("prepared_query") or state.get("query") or ""
        titles: list[str] = []
        seen: set[str] = set()
        for chunk in retriever.chunks:
            if chunk.section.casefold() not in seen:
                seen.add(chunk.section.casefold())
                titles.append(chunk.section)
        broadened = f"{prepared} {' '.join(titles)}".strip()
        return {
            "prepared_query": broadened,
            "retries": int(state.get("retries") or 0) + 1,
            "trace": [_trace("broaden_query", "added section titles", started)],
        }

    def draft_answer(state: RagState) -> dict:
        started = time.perf_counter()
        question = state.get("query") or ""
        passages = list(state.get("passages") or [])
        if not passages or float(passages[0].get("coverage") or 0) < WEAK_COVERAGE:
            return {
                "answer": NOT_FOUND_ANSWER,
                "citations": [],
                "trace": [_trace("draft_answer", "no grounded passage", started)],
            }
        best = passages[0]
        answer = llm.answer(question, best["text"]).strip() or NOT_FOUND_ANSWER
        return {
            "answer": answer,
            "citations": [best["citation"]],
            "trace": [_trace("draft_answer", best["citation"], started)],
        }

    def route_after_grade(state: RagState) -> str:
        passages = list(state.get("passages") or [])
        coverage = float(passages[0].get("coverage") or 0) if passages else 0.0
        if coverage < WEAK_COVERAGE and int(state.get("retries") or 0) < 1:
            return "broaden_query"
        return "draft_answer"

    builder = StateGraph(RagState)
    builder.add_node("prepare_query", prepare_query)
    builder.add_node("retrieve", retrieve)
    builder.add_node("grade_documents", grade_documents)
    builder.add_node("broaden_query", broaden_query)
    builder.add_node("draft_answer", draft_answer)
    builder.add_edge(START, "prepare_query")
    builder.add_edge("prepare_query", "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    builder.add_conditional_edges(
        "grade_documents",
        route_after_grade,
        {"broaden_query": "broaden_query", "draft_answer": "draft_answer"},
    )
    builder.add_edge("broaden_query", "retrieve")
    builder.add_edge("draft_answer", END)
    return builder.compile()


def route_after_grade_name(coverage: float, retries: int) -> str:
    """Pure helper so tests can check the retry decision without the graph."""
    if coverage < WEAK_COVERAGE and retries < 1:
        return "broaden_query"
    return "draft_answer"
