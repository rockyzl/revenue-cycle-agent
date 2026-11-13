import copy

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app import cms, cost_workflow


def sample_state():
    row = {
        "found": True,
        "source_id": "cms:2024:240010:5072",
        "average_submitted_charge": "7825.60",
        "average_medicare_allowed": "1618.39",
        "average_medicare_payment": "1280.16",
    }
    return {
        "question": "Explain the amounts",
        "provider_ccn": "240010",
        "apc_code": "5072",
        "draft": {
            "intent": "charges_explained",
            "summary": "Historical benchmark",
            "response": "The 2024 average submitted charge was $7,825.60.",
            "evidence_ids": [row["source_id"], "cms:definitions:v1"],
            "missing_information": [],
            "needs_specialist": False,
        },
        "tool_trace": [
            {
                "tool": "lookup_cms_costs",
                "input": {"provider_ccn": "240010", "apc_code": "5072"},
                "output": row,
            },
            {
                "tool": "get_cost_definitions",
                "input": {},
                "output": cms.get_cost_definitions(),
            },
        ],
    }


def test_blank_cms_values_stay_unavailable():
    assert cms.money("") is None
    assert cms.money(None) is None
    assert cms.money("0") == "0.00"
    assert cms.money("1618.3881065088") == "1618.39"


@pytest.mark.parametrize("amount", ["$999", "$999.00", "$7,825.61"])
def test_unsupported_dollars_suppress_the_draft(amount):
    state = sample_state()
    state["draft"]["response"] = f"The 2024 average is {amount}."
    result = cost_workflow.check_draft(state)
    assert not result["checks"]["quoted_amounts_match"]
    assert amount not in result["draft"]["response"]
    assert result["routing"]["queue"] == "Cost specialist"


def test_personal_estimate_and_unavailable_data_force_specialist():
    state = sample_state()
    state["draft"]["intent"] = "personal_estimate"
    assert cost_workflow.check_draft(state)["draft"]["needs_specialist"]
    state = sample_state()
    state["tool_trace"][0]["output"]["average_medicare_payment"] = None
    assert cost_workflow.check_draft(state)["draft"]["needs_specialist"]


@pytest.mark.asyncio
async def test_cms_ignoring_filter_is_rejected(monkeypatch):
    async def fake_get(self, url, params):
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json=[{"Rndrng_Prvdr_CCN": "999999", "APC_Cd": "5072"}],
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with pytest.raises(ValueError, match="different provider"):
        await cms.lookup_cms_costs("240010", "5072")


@pytest.mark.asyncio
async def test_edited_review_resumes_and_preserves_original(monkeypatch):
    state = sample_state()

    async def investigate(_):
        return copy.deepcopy(state)

    monkeypatch.setattr(cost_workflow, "investigate", investigate)
    graph = cost_workflow.build_cost_graph(MemorySaver())
    config = {"configurable": {"thread_id": "edited"}}
    first = await graph.ainvoke(
        {k: state[k] for k in ("question", "provider_ccn", "apc_code")}, config
    )
    assert first["__interrupt__"]
    final = await graph.ainvoke(
        Command(
            resume={
                "decision": "approve",
                "edited_response": "Reviewed historical data; please contact the provider for an individual estimate.",
            }
        ),
        config,
    )
    assert final["status"] == "reviewed_draft"
    assert final["approved_response"].startswith("Reviewed historical")
    assert final["draft"]["response"] == state["draft"]["response"]
