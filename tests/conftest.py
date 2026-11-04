import json
from pathlib import Path

import pytest

from podoba_helpdesk.service import ChatService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def service() -> ChatService:
    return ChatService()


@pytest.fixture(scope="session")
def cases() -> list[dict]:
    return json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
