"""In-process load test of the compiled agent.

The run does not go through HTTP or Streamlit. It measures the graph. A second
pass turns on the answer cache so repeated passenger questions can be compared
with the cold path.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from podoba_helpdesk.service import ChatService


QUERIES = 150
WARMUP = 5


def load_questions() -> list[str]:
    cases = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    return [case["question"] for case in cases]


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, int(round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def summarize_latencies(samples: list[dict], elapsed_s: float) -> dict:
    latencies = [sample["latency_ms"] for sample in samples]
    return {
        "queries": len(samples),
        "mean_ms": round(statistics.fmean(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(percentile(latencies, 95), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
        "elapsed_s": round(elapsed_s, 3),
        "throughput_qps": round(len(samples) / elapsed_s, 3) if elapsed_s else 0,
    }


def _walk_trace(steps: list[dict], totals: dict[str, float], counts: dict[str, int]) -> None:
    for step in steps:
        name = step.get("node") or "unknown"
        totals[name] += float(step.get("ms") or 0)
        counts[name] += 1
        _walk_trace(step.get("children") or [], totals, counts)


def node_profile(samples: list[dict]) -> dict:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for sample in samples:
        _walk_trace(sample.get("trace") or [], totals, counts)
    ranked = sorted(totals, key=lambda name: totals[name], reverse=True)
    return {
        name: {
            "total_ms": round(totals[name], 3),
            "calls": counts[name],
            "mean_ms": round(totals[name] / counts[name], 3) if counts[name] else 0,
        }
        for name in ranked
    }


def by_intent(samples: list[dict]) -> dict:
    grouped: dict[str, list[float]] = defaultdict(list)
    for sample in samples:
        grouped[sample["intent"]].append(sample["latency_ms"])
    return {
        intent: {
            "n": len(values),
            "mean_ms": round(statistics.fmean(values), 3),
            "p95_ms": round(percentile(values, 95), 3),
        }
        for intent, values in sorted(grouped.items())
    }


def run_pass(service: ChatService, questions: list[str]) -> tuple[list[dict], float]:
    for index in range(WARMUP):
        service.ask(questions[index % len(questions)])
    samples = []
    started = time.perf_counter()
    for index in range(QUERIES):
        result = service.ask(questions[index % len(questions)])
        samples.append(
            {
                "latency_ms": float(result["latency_ms"]),
                "intent": result["intent"],
                "cache_hit": bool(result.get("cache_hit")),
                "trace": result.get("trace") or [],
            }
        )
    elapsed = time.perf_counter() - started
    return samples, elapsed


def main() -> int:
    questions = load_questions()
    cold_service = ChatService(cache_size=0)
    cold_samples, cold_elapsed = run_pass(cold_service, questions)
    warm_service = ChatService(cache_size=256)
    warm_samples, warm_elapsed = run_pass(warm_service, questions)
    cold_nodes = node_profile(cold_samples)
    bottleneck = next(iter(cold_nodes), "unknown")
    hits = sum(1 for sample in warm_samples if sample["cache_hit"])
    report = {
        "queries": QUERIES,
        "warmup": WARMUP,
        "unique_questions": len(questions),
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "cold": summarize_latencies(cold_samples, cold_elapsed),
        "cached": summarize_latencies(warm_samples, warm_elapsed),
        "cache_hits_in_timed_pass": hits,
        "cold_by_intent": by_intent(cold_samples),
        "cold_nodes": cold_nodes,
        "bottleneck_node": bottleneck,
    }
    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "load_test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    cold = report["cold"]
    cached = report["cached"]
    print(
        f"cold mean {cold['mean_ms']} ms  p95 {cold['p95_ms']} ms  "
        f"max {cold['max_ms']} ms  {cold['throughput_qps']} qps"
    )
    print(
        f"cached mean {cached['mean_ms']} ms  hits {hits}/{QUERIES}  "
        f"bottleneck {bottleneck}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
