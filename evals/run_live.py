"""Run the fixed routing/output evaluation against the configured OpenRouter model."""
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agent import StudyAgent
from app.config import get_settings
from app.llm import OpenRouter


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]


def structure_valid(action, data):
    if action == "study_plan":
        days = data.get("study_days", [])
        return bool(days) and [day.get("day") for day in days] == list(range(1, len(days) + 1))
    if action == "quiz":
        return len(data.get("questions", [])) == 3
    if action == "explain_topic":
        return bool(data.get("key_points")) and bool(data.get("check_question", "").strip())
    return True


def main():
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("Set OPENROUTER_API_KEY before running live evaluations.", file=sys.stderr)
        return 2
    llm = OpenRouter(settings)
    agent = StudyAgent(llm, settings)
    cases = json.loads(Path("evals/cases.json").read_text())
    records = []
    for case in cases:
        started = time.perf_counter()
        result = agent.respond(case["input"], [], {})
        elapsed = time.perf_counter() - started
        model_failure = result.rationale.startswith("Workflow stopped safely after ")
        structured_output_valid = not model_failure and structure_valid(result.action.value, result.data)
        records.append({
            **case,
            "actual": result.action.value,
            "action_correct": result.action.value == case["expected"],
            "nonempty_response": bool(result.text.strip()),
            "structure_valid": structured_output_valid,
            "model_failure": model_failure,
            "response": result.text,
            "rationale": result.rationale,
            "latency_seconds": round(elapsed, 3),
        })
        print(f"{case['id']}: {records[-1]['actual']} ({elapsed:.1f}s)")
    latencies = [r["latency_seconds"] for r in records]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.openrouter_model,
        "case_count": len(records),
        "routing_accuracy": sum(r["action_correct"] for r in records) / len(records),
        "nonempty_response_rate": sum(r["nonempty_response"] for r in records) / len(records),
        "structured_output_valid_rate": sum(r["structure_valid"] for r in records) / len(records),
        "model_failure_count": sum(r["model_failure"] for r in records),
        "latency_seconds": {"mean": round(statistics.mean(latencies), 3), "p50": percentile(latencies, .50), "p95": percentile(latencies, .95)},
        "prompt_tokens": llm.prompt_tokens,
        "completion_tokens": llm.completion_tokens,
        "automated_quality_scope": "Routing label, non-empty output, execution failures, and action-specific structures are checked. Factual correctness and teaching quality require human review using docs/evaluation.md.",
        "cases": records,
    }
    target = Path("eval-results")
    target.mkdir(exist_ok=True)
    output = target / "live-report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    llm.client.close()
    print(f"Routing accuracy: {report['routing_accuracy']:.1%}; report: {output}")
    return 0 if report["routing_accuracy"] >= .8 and report["nonempty_response_rate"] == 1 and report["structured_output_valid_rate"] == 1 and report["model_failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
