from podoba_helpdesk.planner import build_subtasks, classify, split_parts


def test_greetings_and_out_of_scope() -> None:
    assert classify("Hello, who are you?") == "chitchat"
    assert classify("Thanks") == "chitchat"
    assert classify("Hello, how long is a single ticket valid?") == "policy_lookup"
    assert classify("") == "out_of_scope"
    assert classify("What will the weather be in Budapest tomorrow?") == "out_of_scope"
    assert classify("Who won the football match?") == "out_of_scope"


def test_policy_versus_calculators() -> None:
    assert classify("How long is a single ticket valid?") == "policy_lookup"
    assert classify("What does an adult single ticket cost in zone 1?") == "policy_lookup"
    assert classify("How much is an adult single ticket for 3 zones?") == "fare_calc"
    assert classify("How much is an adult single for zone 3?") == "fare_calc"
    assert classify("How much is a child single ticket for 4 zones?") == "fare_calc"
    bands = "The train was 45 minutes late. Which compensation price band applies?"
    assert classify(bands) == "policy_lookup"
    delay = "The train was 45 minutes late and the ticket cost 8.00 EUR. How much compensation do I get?"
    assert classify(delay) == "delay_compensation"
    assert classify("The train was 12 minutes late and the ticket cost 6.40 EUR.") == "delay_compensation"


def test_multi_part_splits_tool_and_retrieval() -> None:
    question = "How much is an adult single ticket for 2 zones, and how long is lost property kept?"
    assert classify(question) == "multi_part"
    parts = split_parts(question)
    assert len(parts) == 2
    tasks = build_subtasks(question, "multi_part")
    assert [task["kind"] for task in tasks] == ["tool", "rag"]
    assert tasks[0]["tool"] == "calculate_fare"
    assert tasks[0]["query"] != tasks[1]["query"]
    assert "lost property" in tasks[1]["query"]


def test_two_retrieval_parts_stay_independent() -> None:
    question = "How long is a single ticket valid, and how long is lost property kept?"
    tasks = build_subtasks(question, "multi_part")
    assert [task["kind"] for task in tasks] == ["rag", "rag"]
    assert tasks[0]["query"].casefold().startswith("how long is a single ticket")
    assert "lost property" in tasks[1]["query"]
