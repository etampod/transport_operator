from fastapi.testclient import TestClient

from api.main import app


def test_health_and_chat() -> None:
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["documents"] == 9
    assert body["chunks"] > 20
    assert "calculate_fare" in body["tools"]
    assert "assess_delay_compensation" in body["tools"]

    reply = client.post("/chat", json={"query": "How long is a single ticket valid?"})
    assert reply.status_code == 200
    payload = reply.json()
    assert "90 minutes" in payload["answer"]
    assert payload["intent"] == "policy_lookup"
    assert payload["model"] == "dummy-extractive-v1"

    empty = client.post("/chat", json={"query": ""})
    assert empty.status_code == 422
    blank = client.post("/chat", json={"query": "   "})
    assert blank.status_code == 400
