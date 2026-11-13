"""Run the six public cases against live CMS + the configured real model."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from langgraph.types import Command

from app.agent import LLM, MODE
from app.cost_api import CASES
from app.cost_workflow import web_graph


async def main():
    results = []
    for case in CASES:
        config = {"configurable": {"thread_id": "eval-cms-" + case["id"]}}
        try:
            first = await web_graph.ainvoke(
                {k: case[k] for k in ("question", "provider_ccn", "apc_code")}, config
            )
            state = (await web_graph.aget_state(config)).values
            passed = bool(first.get("__interrupt__")) and all(state["checks"].values())
            if case["id"] in {"personal", "dispute", "unavailable", "missing"}:
                passed = passed and state["draft"]["needs_specialist"]
            final = await web_graph.ainvoke(
                Command(
                    resume={
                        "decision": "reject",
                        "comment": "Automated evaluation only",
                    }
                ),
                config,
            )
            passed = passed and final["status"] == "rejected"
            results.append({"case_id": case["id"], "passed": passed, "state": state})
        except Exception as exc:
            results.append(
                {
                    "case_id": case["id"],
                    "passed": False,
                    "error_type": type(exc).__name__,
                }
            )
        print(case["id"], "PASS" if results[-1]["passed"] else "FAIL", flush=True)
        report = {
            "at": datetime.now(UTC).isoformat(),
            "mode": MODE,
            "model": LLM,
            "data": "Live CMS API; 2024 public hospital/service aggregates",
            "scope": "Six hand-authored smoke cases, not a production quality estimate or semantic validation.",
            "passed": sum(r["passed"] for r in results),
            "cases": len(results),
            "results": results,
        }
        Path("artifacts/eval-cms-live.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
