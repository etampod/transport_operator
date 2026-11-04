"""Service wrapper around the compiled graphs."""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path

from podoba_helpdesk.config import CORPUS_DIR
from podoba_helpdesk.corpus import load_corpus
from podoba_helpdesk.graph import build_graph
from podoba_helpdesk.llm import LLM, build_llm
from podoba_helpdesk.rag_graph import build_rag_subgraph
from podoba_helpdesk.retriever import BM25Retriever
from podoba_helpdesk.state import initial_state
from podoba_helpdesk.textutil import normalize_ws
from podoba_helpdesk.tools import TOOL_RUNNERS

# A long multi-part question walks select/run once per part. The default
# LangGraph limit of 25 steps is enough for two parts and tight beyond that.
_RECURSION_LIMIT = 80


def _cache_size_from_env() -> int:
    raw = os.environ.get("AGENT_CACHE_SIZE", "0").strip()
    try:
        value = int(raw)
    except ValueError:
        return 0
    return max(value, 0)


class ChatService:
    def __init__(
        self,
        corpus_dir: Path | None = None,
        llm: LLM | None = None,
        cache_size: int | None = None,
    ) -> None:
        self.corpus = load_corpus(corpus_dir or CORPUS_DIR)
        self.retriever = BM25Retriever(self.corpus)
        self.llm = llm or build_llm()
        self.rag = build_rag_subgraph(self.retriever, self.llm)
        self.graph = build_graph(self.retriever, self.llm, rag=self.rag)
        if cache_size is None:
            cache_size = _cache_size_from_env()
        self.cache_size = max(cache_size, 0)
        self._cache: dict[str, dict] = {}

    def describe(self) -> dict:
        return {
            "service": "podoba-transit-helpdesk",
            "model": self.llm.name,
            "documents": len(self.corpus.document_ids),
            "chunks": len(self.corpus.chunks),
            "tools": sorted(TOOL_RUNNERS),
            "document_ids": self.corpus.document_ids,
            "cache_size": self.cache_size,
        }

    def ask(self, query: str) -> dict:
        text = normalize_ws(query)
        if not text:
            raise ValueError("Query is empty.")
        key = text.casefold()
        if self.cache_size > 0 and key in self._cache:
            stored = self._cache.pop(key)
            self._cache[key] = stored
            cached = copy.deepcopy(stored)
            cached["cache_hit"] = True
            cached["latency_ms"] = 0.0
            return cached
        started = time.perf_counter()
        state = self.graph.invoke(initial_state(text), config={"recursion_limit": _RECURSION_LIMIT})
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        result = _public_result(state, latency_ms, cache_hit=False, model=self.llm.name)
        if self.cache_size > 0:
            self._cache[key] = copy.deepcopy(result)
            while len(self._cache) > self.cache_size:
                oldest = next(iter(self._cache))
                self._cache.pop(oldest, None)
        return result

    def ask_retrieval_only(self, query: str) -> dict:
        """Call the RAG subgraph directly, with no routing and no calculators."""
        text = normalize_ws(query)
        if not text:
            raise ValueError("Query is empty.")
        started = time.perf_counter()
        state = self.rag.invoke(
            {"query": text, "retries": 0},
            config={"recursion_limit": _RECURSION_LIMIT},
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "answer": state.get("answer") or "",
            "citations": list(state.get("citations") or []),
            "passages": list(state.get("passages") or []),
            "trace": list(state.get("trace") or []),
            "latency_ms": latency_ms,
            "intent": "retrieval_only",
        }


def _public_result(state: dict, latency_ms: float, cache_hit: bool, model: str) -> dict:
    return {
        "answer": state.get("final_answer") or "",
        "intent": state.get("intent") or "",
        "citations": list(state.get("citations") or []),
        "passages": list(state.get("passages") or []),
        "intermediate_results": list(state.get("intermediate_results") or []),
        "subtasks": list(state.get("subtasks") or []),
        "trace": list(state.get("trace") or []),
        "latency_ms": latency_ms,
        "cache_hit": cache_hit,
        "model": model,
    }
