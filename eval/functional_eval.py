"""Functional evaluation of the full workflow, plus a retrieval-only baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from podoba_helpdesk.scoring import evaluate_case
from podoba_helpdesk.service import ChatService


def load_cases() -> list[dict]:
    return json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))


def _accuracy(rows: list[dict], field: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row[field]) / len(rows), 3)


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    passed = sum(1 for row in rows if row["ok"])
    latencies = [float(row["latency_ms"] or 0) for row in rows]
    citation_ok = sum(
        1 for row in rows if not row["missing_docs"] and not row["unexpected_citations"]
    )
    keyword_ok = sum(1 for row in rows if not row["missing"] and not row["forbidden"])
    return {
        "n": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "intent_accuracy": _accuracy(rows, "intent_ok"),
        "keyword_accuracy": round(keyword_ok / total, 3) if total else 0,
        "citation_accuracy": round(citation_ok / total, 3) if total else 0,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0,
    }


def run(service: ChatService | None = None) -> dict:
    service = service or ChatService()
    cases = load_cases()
    agent_rows = []
    retrieval_rows = []
    for case in cases:
        agent = service.ask(case["question"])
        agent_rows.append(evaluate_case(agent, case))
        retrieved = service.ask_retrieval_only(case["question"])
        retrieval_rows.append(evaluate_case(retrieved, case, check_intent=False))
    return {
        "agent": summarize(agent_rows),
        "retrieval_only": summarize(retrieval_rows),
        "rows": agent_rows,
        "retrieval_rows": retrieval_rows,
    }


def _markdown(report: dict) -> str:
    agent = report["agent"]
    baseline = report["retrieval_only"]
    lines = [
        "# Functional evaluation",
        "",
        f"Full workflow: **{agent['passed']} of {agent['n']} passed**.",
        "",
        f"- Intent accuracy: {agent['intent_accuracy']}",
        f"- Required-phrase accuracy: {agent['keyword_accuracy']}",
        f"- Citation accuracy: {agent['citation_accuracy']}",
        f"- Mean latency: {agent['mean_latency_ms']} ms",
        "",
        "Retrieval-only baseline (RAG subgraph, no router and no calculators),",
        "scored on the same phrases and documents, ignoring intent:",
        "",
        f"- Passed: {baseline['passed']} of {baseline['n']}",
        f"- Required-phrase accuracy: {baseline['keyword_accuracy']}",
        f"- Citation accuracy: {baseline['citation_accuracy']}",
        "",
        "| ID | Intent | OK | Answer |",
        "| --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        answer = " ".join(row["answer"].split())
        if len(answer) > 220:
            answer = answer[:217] + "..."
        answer = answer.replace("|", "\\|")
        flag = "pass" if row["ok"] else "fail"
        lines.append(f"| {row['id']} | {row['intent']} | {flag} | {answer} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    report = run()
    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "functional_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "functional_report.md").write_text(_markdown(report), encoding="utf-8")
    agent = report["agent"]
    print(
        f"agent {agent['passed']}/{agent['n']}  "
        f"intent {agent['intent_accuracy']}  "
        f"phrases {agent['keyword_accuracy']}  "
        f"citations {agent['citation_accuracy']}  "
        f"mean {agent['mean_latency_ms']} ms"
    )
    print(
        f"retrieval-only phrases {report['retrieval_only']['keyword_accuracy']}  "
        f"passed {report['retrieval_only']['passed']}/{report['retrieval_only']['n']}"
    )
    failed = [row for row in report["rows"] if not row["ok"]]
    for row in failed:
        print(f"FAIL {row['id']} missing={row['missing']} forbid={row['forbidden']} docs={row['missing_docs']} intent={row['intent']}")
        print(row["answer"])
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
