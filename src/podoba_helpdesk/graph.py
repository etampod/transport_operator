"""Main LangGraph workflow.

Nodes
-----
normalize_query
    Collapse whitespace and apply a few surface synonyms. The original question
    stays in `query`.
classify_intent
    Choose chitchat, out_of_scope, multi_part, fare_calc, delay_compensation,
    or policy_lookup.
direct_reply
    Answer greetings and out-of-scope questions without retrieval.
decompose
    Split an in-domain question into independent subtasks.
select_next_subtask
    Dispatch the next pending subtask, or stop when none remain.
run_rag
    Call the compiled RAG subgraph for one subtask. Those nodes are not nodes
    of this graph.
run_tool
    Call a non-retrieval tool for one subtask.
synthesize
    Join intermediate results into one draft. This is the only node that reads them.
finalize
    Attach citations and the customer-service disclaimer.

Conditional routing after classification and after each subtask is the decision
point. A subtask receives only its own query.
"""

from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph

from podoba_helpdesk.config import CHITCHAT_ANSWER, DISCLAIMER, OUT_OF_SCOPE_ANSWER
from podoba_helpdesk.llm import LLM
from podoba_helpdesk.planner import build_subtasks, classify
from podoba_helpdesk.rag_graph import build_rag_subgraph
from podoba_helpdesk.retriever import BM25Retriever
from podoba_helpdesk.state import AgentState
from podoba_helpdesk.textutil import apply_synonyms, normalize_ws
from podoba_helpdesk.tools import TOOL_RUNNERS


def _mark_done(subtasks: list[dict], task_id: int) -> list[dict]:
    updated = []
    for task in subtasks:
        if task["id"] == task_id:
            updated.append({**task, "status": "done"})
        else:
            updated.append(dict(task))
    return updated


def _trace(node: str, detail: str, started: float, children: list[dict] | None = None) -> dict:
    item = {
        "node": node,
        "detail": detail,
        "ms": round((time.perf_counter() - started) * 1000, 3),
    }
    if children:
        item["children"] = children
    return item


def _collect_citations(state: AgentState) -> list[str]:
    citations: list[str] = []
    results = sorted(state.get("intermediate_results") or [], key=lambda item: item["id"])
    for result in results:
        for label in result.get("citations") or []:
            if label not in citations:
                citations.append(label)
    return citations


def route_after_classify(state: AgentState) -> str:
    if state.get("intent") in {"chitchat", "out_of_scope"}:
        return "direct_reply"
    return "decompose"


def route_subtask(state: AgentState) -> str:
    current = state.get("current_subtask") or {}
    if current.get("status") != "pending":
        return "synthesize"
    if current.get("kind") == "tool":
        return "run_tool"
    return "run_rag"


def build_graph(retriever: BM25Retriever, llm: LLM, rag=None):
    rag = rag or build_rag_subgraph(retriever, llm)

    def normalize_query(state: AgentState) -> dict:
        started = time.perf_counter()
        original = normalize_ws(state.get("query") or "")
        working = apply_synonyms(original)
        detail = "unchanged" if working == original else "synonyms applied"
        return {
            "query": original,
            "working_query": working,
            "trace": [_trace("normalize_query", detail, started)],
        }

    def classify_intent(state: AgentState) -> dict:
        started = time.perf_counter()
        intent = classify(state.get("working_query") or state.get("query") or "")
        return {
            "intent": intent,
            "trace": [_trace("classify_intent", intent, started)],
        }

    def direct_reply(state: AgentState) -> dict:
        started = time.perf_counter()
        intent = state.get("intent")
        text = CHITCHAT_ANSWER if intent == "chitchat" else OUT_OF_SCOPE_ANSWER
        return {
            "draft_answer": text,
            "trace": [_trace("direct_reply", intent or "reply", started)],
        }

    def decompose(state: AgentState) -> dict:
        started = time.perf_counter()
        working = state.get("working_query") or state.get("query") or ""
        subtasks = build_subtasks(working, state.get("intent") or "policy_lookup")
        detail = ", ".join(f"{task['id']}:{task['kind']}" for task in subtasks) or "no subtasks"
        return {
            "subtasks": subtasks,
            "trace": [_trace("decompose", detail, started)],
        }

    def select_next_subtask(state: AgentState) -> dict:
        started = time.perf_counter()
        for task in state.get("subtasks") or []:
            if task.get("status") == "pending":
                detail = f"subtask {task['id']} via {task['kind']}"
                return {
                    "current_subtask": dict(task),
                    "trace": [_trace("select_next_subtask", detail, started)],
                }
        return {
            "current_subtask": {},
            "trace": [_trace("select_next_subtask", "all subtasks complete", started)],
        }

    def run_rag(state: AgentState) -> dict:
        started = time.perf_counter()
        task = state["current_subtask"]
        # Isolated input: the subgraph sees this subtask only.
        rag_state = rag.invoke({"query": task["query"], "retries": 0})
        result = {
            "id": task["id"],
            "kind": "rag",
            "query": task["query"],
            "answer": rag_state.get("answer", ""),
            "citations": list(rag_state.get("citations") or []),
        }
        passages = []
        for passage in rag_state.get("passages") or []:
            copied = dict(passage)
            copied["subtask_id"] = task["id"]
            passages.append(copied)
        return {
            "subtasks": _mark_done(state.get("subtasks") or [], task["id"]),
            "current_subtask": {},
            "intermediate_results": [result],
            "passages": passages,
            "trace": [_trace("run_rag", task["query"], started, list(rag_state.get("trace") or []))],
        }

    def run_tool(state: AgentState) -> dict:
        started = time.perf_counter()
        task = state["current_subtask"]
        runner = TOOL_RUNNERS[task["tool"]]
        tool_state = runner(task["query"])
        result = {
            "id": task["id"],
            "kind": "tool",
            "tool": task["tool"],
            "query": task["query"],
            "answer": tool_state["answer"],
            "citations": list(tool_state.get("citations") or []),
        }
        return {
            "subtasks": _mark_done(state.get("subtasks") or [], task["id"]),
            "current_subtask": {},
            "intermediate_results": [result],
            "trace": [_trace("run_tool", task["tool"], started)],
        }

    def synthesize(state: AgentState) -> dict:
        started = time.perf_counter()
        results = sorted(state.get("intermediate_results") or [], key=lambda item: item["id"])
        if not results:
            draft = "I could not find a Podoba Transit rule that answers this question."
        elif len(results) == 1:
            draft = results[0]["answer"]
        else:
            draft = "\n\n".join(f"Part {item['id']}: {item['answer']}" for item in results)
        return {
            "draft_answer": draft,
            "trace": [_trace("synthesize", f"{len(results)} intermediate results", started)],
        }

    def finalize(state: AgentState) -> dict:
        started = time.perf_counter()
        intent = state.get("intent") or ""
        draft = (state.get("draft_answer") or "").strip()
        if intent in {"chitchat", "out_of_scope"}:
            final = draft
            citations: list[str] = []
        else:
            final = f"{draft}\n\n{DISCLAIMER}" if draft else DISCLAIMER
            citations = _collect_citations(state)
        return {
            "final_answer": final,
            "citations": citations,
            "trace": [_trace("finalize", f"{len(citations)} citations", started)],
        }

    builder = StateGraph(AgentState)
    builder.add_node("normalize_query", normalize_query)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("direct_reply", direct_reply)
    builder.add_node("decompose", decompose)
    builder.add_node("select_next_subtask", select_next_subtask)
    builder.add_node("run_rag", run_rag)
    builder.add_node("run_tool", run_tool)
    builder.add_node("synthesize", synthesize)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "normalize_query")
    builder.add_edge("normalize_query", "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {"direct_reply": "direct_reply", "decompose": "decompose"},
    )
    builder.add_edge("decompose", "select_next_subtask")
    builder.add_conditional_edges(
        "select_next_subtask",
        route_subtask,
        {"run_rag": "run_rag", "run_tool": "run_tool", "synthesize": "synthesize"},
    )
    builder.add_edge("run_rag", "select_next_subtask")
    builder.add_edge("run_tool", "select_next_subtask")
    builder.add_edge("direct_reply", "finalize")
    builder.add_edge("synthesize", "finalize")
    builder.add_edge("finalize", END)
    compiled = builder.compile()
    return compiled


def node_names(graph) -> set[str]:
    drawable = graph.get_graph()
    raw_nodes = getattr(drawable, "nodes", {})
    if isinstance(raw_nodes, dict):
        names = set(raw_nodes)
    else:
        names = {getattr(node, "id", str(node)) for node in raw_nodes}
    return {name for name in names if name not in {"__start__", "__end__"}}
