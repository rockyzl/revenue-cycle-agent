"""Evaluate workflow contracts separately from model-mode case checks.

This hand-authored eight-case set is a smoke evaluation, not clinical validation,
robustness certification, or a production accuracy estimate.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from langgraph.types import Command

from app.agent import LLM, MODE
from app.workflow import demo_graph


async def main():
    cases = json.loads(Path("tests/eval/datasets/billing-cases.json").read_text())
    results = []
    for case in cases:
        config = {"configurable": {"thread_id": f"eval-{MODE}-{case['id']}"}}
        try:
            first = await demo_graph.ainvoke(
                {"message": case["message"], "bill_id": case["bill_id"]}, config
            )
            state = (await demo_graph.aget_state(config)).values
            triage = state["triage"]
            checks = {
                "paused_for_review": bool(first.get("__interrupt__")),
                "category": triage["category"] == case["category"],
                "escalation": triage["needs_specialist"] == case["needs_specialist"],
                "reference_ids": state["evidence_verified"],
            }
            if "contains" in case:
                checks["expected_fact"] = (
                    case["contains"].lower() in triage["draft_response"].lower()
                )
            final = await demo_graph.ainvoke(
                Command(resume={"decision": "reject", "comment": "Evaluation only"}),
                config,
            )
            checks["rejection_resumes"] = final["status"] == "rejected"
            row = {
                "id": case["id"],
                "checks": checks,
                "passed": all(checks.values()),
                "triage": triage,
                "tool_calls": state["tool_calls"],
            }
        except Exception as exc:
            row = {"id": case["id"], "passed": False, "error_type": type(exc).__name__}
        results.append(row)
        print(case["id"], "PASS" if row["passed"] else "FAIL", flush=True)
    report = {
        "mode": MODE,
        "model": LLM if MODE == "vertex" else None,
        "at": datetime.now(UTC).isoformat(),
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "scope": "Eight hand-authored synthetic smoke cases; replay is not a model evaluation. Reference checks do not establish full factual faithfulness.",
        "results": results,
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path(f"artifacts/eval-{MODE}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['passed']}/{report['cases']} cases passed in {MODE} mode")
    raise SystemExit(0 if report["passed"] == report["cases"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
