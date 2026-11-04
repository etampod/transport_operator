"""HTTP API for the Podoba Transit assistant."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from podoba_helpdesk.service import ChatService

app = FastAPI(title="Podoba Transit Customer Service", version="1.0.0")
_service: ChatService | None = None


def get_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health() -> dict:
    payload = get_service().describe()
    payload["status"] = "ok"
    return payload


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    try:
        result = get_service().ask(request.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["model"] = get_service().llm.name
    return result
