import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from app.billing import POLICY, Triage, lookup_demo_bill
from app.workflow import ReviewDecision, build_graph, verify_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision,expected", [("approve", "reviewed_draft"), ("reject", "rejected")]
)
async def test_draft_pauses_then_records_review(decision, expected):
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": decision}}
    first = await graph.ainvoke(
        {"message": "What do I owe?", "bill_id": "DEMO-1001"}, config
    )
    assert first["__interrupt__"]
    snapshot = await graph.aget_state(config)
    assert snapshot.values["status"] == "awaiting_review"
    assert snapshot.values.get("review") is None
    final = await graph.ainvoke(Command(resume={"decision": decision}), config)
    assert final["status"] == expected
    assert not (await graph.aget_state(config)).next


def test_unknown_bill_does_not_invent_financial_data():
    result = lookup_demo_bill("DEMO-MISSING")
    assert result["found"] is False
    assert "balance_usd" not in result


def test_bad_reference_suppresses_draft():
    triage = Triage(
        category="balance",
        summary="x",
        draft_response="Invented amount $900.",
        evidence_ids=["made-up"],
        needs_specialist=False,
    )
    result = verify_evidence({"bill_id": "DEMO-1001", "triage": triage.model_dump()})
    assert result["evidence_verified"] is False
    assert "900" not in result["triage"]["draft_response"]
    assert result["triage"]["needs_specialist"] is True


def test_dispute_cannot_be_marked_routine_by_model():
    triage = Triage(
        category="dispute",
        summary="Duplicate charge",
        draft_response="Please review.",
        evidence_ids=["fixture:DEMO-1001:v1", POLICY["source_id"]],
        needs_specialist=False,
    )
    result = verify_evidence({"bill_id": "DEMO-1001", "triage": triage.model_dump()})
    assert result["triage"]["needs_specialist"] is True


def test_review_rejects_unrecognized_decision_and_extra_actions():
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate({"decision": "send"})
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate({"decision": "approve", "refund": 125})
