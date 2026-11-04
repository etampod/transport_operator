"""Parent-graph state.

`intermediate_results` holds one record per finished subtask. A subtask node
receives only `current_subtask` and does not read sibling results. Append-only
reducers keep one branch from replacing another branch's output.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    working_query: str
    intent: str
    subtasks: list[dict]
    current_subtask: dict
    intermediate_results: Annotated[list[dict], operator.add]
    passages: Annotated[list[dict], operator.add]
    trace: Annotated[list[dict], operator.add]
    draft_answer: str
    final_answer: str
    citations: list[str]


def initial_state(query: str) -> AgentState:
    return {
        "query": query,
        "working_query": "",
        "intent": "",
        "subtasks": [],
        "current_subtask": {},
        "intermediate_results": [],
        "passages": [],
        "trace": [],
        "draft_answer": "",
        "final_answer": "",
        "citations": [],
    }
