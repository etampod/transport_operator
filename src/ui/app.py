"""Streamlit prototype.

The page shows the answer, the citations, every agent step, and the passages
the RAG subgraph kept. Set AGENT_API_URL to call the API service instead of
loading the graph inside the UI process.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import streamlit as st

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from podoba_helpdesk.config import EXAMPLE_QUESTIONS
from podoba_helpdesk.service import ChatService


st.set_page_config(page_title="Podoba Transit Helpdesk", layout="wide")


@st.cache_resource
def _local_service() -> ChatService:
    return ChatService()


def ask(query: str) -> dict:
    api_url = os.environ.get("AGENT_API_URL", "").rstrip("/")
    if api_url:
        response = httpx.post(f"{api_url}/chat", json={"query": query}, timeout=60.0)
        response.raise_for_status()
        return response.json()
    result = _local_service().ask(query)
    result["model"] = _local_service().llm.name
    return result


def describe() -> dict:
    api_url = os.environ.get("AGENT_API_URL", "").rstrip("/")
    if api_url:
        response = httpx.get(f"{api_url}/health", timeout=30.0)
        response.raise_for_status()
        return response.json()
    info = _local_service().describe()
    info["status"] = "ok"
    return info


def _render_trace(trace: list[dict], depth: int = 0) -> None:
    for step in trace:
        indent = "· " * depth
        st.markdown(
            f"`{indent}{step.get('node', '')}` ({float(step.get('ms', 0)):.2f} ms) — {step.get('detail', '')}"
        )
        children = step.get("children") or []
        if children:
            _render_trace(children, depth + 1)


def _render_result(result: dict) -> None:
    st.markdown(result.get("answer") or "")
    citations = result.get("citations") or []
    if citations:
        st.caption("Sources: " + "; ".join(citations))
    meta = st.columns(3)
    meta[0].metric("Intent", result.get("intent") or "—")
    meta[1].metric("Latency", f"{float(result.get('latency_ms') or 0):.1f} ms")
    meta[2].metric("Passages", len(result.get("passages") or []))

    with st.expander("Agent steps", expanded=True):
        _render_trace(result.get("trace") or [])
    with st.expander("Subtasks and intermediate results", expanded=True):
        results = result.get("intermediate_results") or []
        if not results:
            st.write("This path did not run a subtask.")
        for item in results:
            label = item.get("tool") or item.get("kind")
            st.markdown(f"**Subtask {item.get('id')} · {label}**")
            st.caption(item.get("query", ""))
            st.write(item.get("answer", ""))
    with st.expander("RAG passages", expanded=False):
        passages = result.get("passages") or []
        if not passages:
            st.write("No retrieval was needed for this answer.")
        for passage in passages:
            st.markdown(
                f"**{passage.get('doc_id')} — {passage.get('section')}**  \n"
                f"score {float(passage.get('score') or 0):.3f} · "
                f"coverage {float(passage.get('coverage') or 0):.2f}"
            )
            st.write(passage.get("text", ""))


def _apply_example() -> None:
    choice = st.session_state.get("example", "")
    if choice and choice != "Write your own question":
        st.session_state["question"] = choice


def main() -> None:
    st.title("Podoba Transit — Customer Service")
    st.write(
        "Agentic RAG prototype for passenger rules. The assistant classifies the question, "
        "splits multi-part questions, retrieves the governing section or calculates a fare "
        "or a delay payment, then cites the rule it used."
    )
    try:
        info = describe()
        st.caption(
            f"Model `{info.get('model', 'unknown')}` · "
            f"{info.get('documents', 0)} policy documents · "
            f"{info.get('chunks', 0)} sections · "
            f"tools {', '.join(info.get('tools') or [])}"
        )
    except Exception as exc:  # noqa: BLE001 - show the connection error in the page
        st.error(f"The assistant is not available: {exc}")
        return

    st.selectbox(
        "Examples",
        ["Write your own question", *EXAMPLE_QUESTIONS],
        key="example",
        on_change=_apply_example,
    )
    query = st.text_area("Question", key="question", height=100)
    if st.button("Ask", type="primary") and query.strip():
        try:
            result = ask(query.strip())
        except Exception as exc:  # noqa: BLE001
            st.error(f"The request failed: {exc}")
        else:
            _render_result(result)


main()
