from podoba_helpdesk.scoring import evaluate_case


def test_evaluation_set_size(cases: list[dict]) -> None:
    assert 10 <= len(cases) <= 20


def test_full_workflow_cases(service, cases: list[dict]) -> None:
    failures = []
    for case in cases:
        result = service.ask(case["question"])
        scored = evaluate_case(result, case)
        if not scored["ok"]:
            failures.append(
                {
                    "id": case["id"],
                    "intent": result["intent"],
                    "missing": scored["missing"],
                    "forbidden": scored["forbidden"],
                    "missing_docs": scored["missing_docs"],
                    "unexpected_citations": scored["unexpected_citations"],
                    "answer": result["answer"],
                    "citations": result["citations"],
                }
            )
    assert failures == []


def test_calculators_beat_retrieval_on_computed_amounts(service) -> None:
    question = "How much is an adult single ticket for 3 zones?"
    agent = service.ask(question)
    retrieved = service.ask_retrieval_only(question)
    assert "4.80 EUR" in agent["answer"]
    assert "4.80 EUR" not in retrieved["answer"]


def test_claim_window_and_strike_rules_are_retrievable(service) -> None:
    claim = service.ask("How many days do I have to submit a delay compensation claim?")
    assert claim["intent"] == "policy_lookup"
    assert "28 days" in claim["answer"]
    assert "POL-DELAY" in " ".join(claim["citations"])

    strike = service.ask("Is compensation paid when a strike was announced 48 hours in advance?")
    assert "not paid" in strike["answer"]
    assert "Announced strikes" in " ".join(strike["citations"])


def test_a_shorter_document_id_does_not_match() -> None:
    result = {
        "answer": "An adult single ticket costs 2.40 EUR in zone 1.",
        "intent": "policy_lookup",
        "citations": ["POL-FARE — Adult single tickets"],
        "latency_ms": 1,
    }
    case = {
        "id": "prefix",
        "question": "fare",
        "expected_intent": "policy_lookup",
        "must_include": [],
        "forbid": [],
        "expect_docs": ["POL-FA"],
    }
    assert evaluate_case(result, case)["missing_docs"] == ["POL-FA"]
