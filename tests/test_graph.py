from podoba_helpdesk.graph import build_graph, node_names, route_after_classify, route_subtask
from podoba_helpdesk.llm import ExtractiveLLM
from podoba_helpdesk.rag_graph import build_rag_subgraph, route_after_grade_name
from podoba_helpdesk.service import ChatService


MAIN = {
    "normalize_query",
    "classify_intent",
    "direct_reply",
    "decompose",
    "select_next_subtask",
    "run_rag",
    "run_tool",
    "synthesize",
    "finalize",
}
RAG = {
    "prepare_query",
    "retrieve",
    "grade_documents",
    "broaden_query",
    "draft_answer",
}


def test_parent_has_at_least_five_nodes_and_rag_is_separate(service: ChatService) -> None:
    parent = node_names(service.graph)
    child = node_names(service.rag)
    assert parent == MAIN
    assert len(parent) >= 5
    assert child == RAG
    assert parent.isdisjoint(child)


def test_routes() -> None:
    assert route_after_classify({"intent": "chitchat"}) == "direct_reply"
    assert route_after_classify({"intent": "out_of_scope"}) == "direct_reply"
    assert route_after_classify({"intent": "policy_lookup"}) == "decompose"
    assert route_subtask({"current_subtask": {"status": "pending", "kind": "rag"}}) == "run_rag"
    assert route_subtask({"current_subtask": {"status": "pending", "kind": "tool"}}) == "run_tool"
    assert route_subtask({"current_subtask": {}}) == "synthesize"
    assert route_after_grade_name(0.1, 0) == "broaden_query"
    assert route_after_grade_name(0.1, 1) == "draft_answer"
    assert route_after_grade_name(0.8, 0) == "draft_answer"


def test_graphs_can_be_built_twice() -> None:
    service = ChatService()
    again = build_graph(service.retriever, ExtractiveLLM(), rag=build_rag_subgraph(service.retriever, service.llm))
    assert "run_rag" in node_names(again)


def test_chitchat_skips_retrieval_and_tools(service: ChatService) -> None:
    result = service.ask("Hello, who are you?")
    nodes = [step["node"] for step in result["trace"]]
    assert nodes == ["normalize_query", "classify_intent", "direct_reply", "finalize"]
    assert result["citations"] == []
    assert result["intermediate_results"] == []


def test_multi_part_results_do_not_share_a_query(service: ChatService) -> None:
    result = service.ask(
        "How much is an adult single ticket for 2 zones, and how long is lost property kept?"
    )
    results = sorted(result["intermediate_results"], key=lambda item: item["id"])
    assert [item["kind"] for item in results] == ["tool", "rag"]
    assert results[0]["query"] != results[1]["query"]
    assert "3.60 EUR" in results[0]["answer"]
    assert "30 days" in results[1]["answer"]
    assert "3.60" not in results[1]["answer"]
    rag_steps = [step for step in result["trace"] if step["node"] == "run_rag"]
    assert rag_steps and rag_steps[0]["children"]
    child_nodes = [step["node"] for step in rag_steps[0]["children"]]
    assert "prepare_query" in child_nodes
    assert "draft_answer" in child_nodes


def test_unknown_retrieval_broadens_once(service: ChatService) -> None:
    result = service.ask_retrieval_only("purple widgets from nowhere")
    nodes = [step["node"] for step in result["trace"]]
    assert nodes.count("broaden_query") == 1
    assert nodes.count("retrieve") == 2
    assert "could not find" in result["answer"].casefold()
    assert result["citations"] == []


def test_cache_drops_the_least_recently_used_question() -> None:
    service = ChatService(cache_size=2)
    service.ask("How long is a single ticket valid?")
    service.ask("How long is lost property kept?")
    assert service.ask("How long is a single ticket valid?")["cache_hit"] is True
    service.ask("What is the penalty fare for travelling without a valid ticket?")
    assert service.ask("How long is a single ticket valid?")["cache_hit"] is True
    assert service.ask("How long is lost property kept?")["cache_hit"] is False


def test_bad_cache_size_does_not_crash(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_CACHE_SIZE", "lots")
    service = ChatService()
    assert service.cache_size == 0
    assert "90 minutes" in service.ask("How long is a single ticket valid?")["answer"]


def test_bike_synonym_reaches_the_bicycle_rule(service: ChatService) -> None:
    result = service.ask("Can I take a bike on a train arriving in the city centre at 08:15?")
    assert result["intent"] == "policy_lookup"
    assert "POL-SAFE" in " ".join(result["citations"])
    assert "not allowed" in result["answer"]
