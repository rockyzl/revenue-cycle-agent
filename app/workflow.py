# Adapted from UiPath's ticket-classification and suspend/resume samples (MIT).
# Copyright (c) UiPath. Full notice: THIRD_PARTY_NOTICES.txt.
import json
import os
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from app.agent import MODE, root_agent
from app.billing import POLICY, Triage, lookup_demo_bill


class GraphInput(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    bill_id: str = Field(pattern=r"^DEMO-[A-Z0-9]+$", max_length=40)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    comment: str = Field(default="", max_length=500)


class GraphState(TypedDict, total=False):
    message: str
    bill_id: str
    triage: dict
    mode: str
    status: str
    evidence_verified: bool
    tool_calls: list[str]
    review: dict


class GraphOutput(BaseModel):
    triage: dict = Field(default_factory=dict)
    mode: str = "replay"
    status: str = "pending"
    evidence_verified: bool = False
    tool_calls: list[str] = Field(default_factory=list)
    review: dict = Field(default_factory=dict)


async def classify(state: GraphState) -> dict:
    request = GraphInput.model_validate(state)
    response = await root_agent.ainvoke(
        {"messages": [HumanMessage(content=request.model_dump_json())]},
        {"recursion_limit": 12},
    )
    if MODE == "replay":
        triage = Triage.model_validate_json(response["messages"][-1].content)
        tools = ["lookup_demo_bill (replay)", "get_demo_policy (replay)"]
    else:
        triage = Triage.model_validate(response["structured_response"])
        tools = [
            call["name"]
            for msg in response["messages"]
            for call in getattr(msg, "tool_calls", [])
            if call["name"] in {"lookup_demo_bill", "get_demo_policy"}
        ]
    return {
        "triage": triage.model_dump(),
        "mode": MODE,
        "status": "drafted",
        "tool_calls": tools,
    }


def verify_evidence(state: GraphState) -> dict:
    bill = lookup_demo_bill(state["bill_id"])
    required = {bill["source_id"], POLICY["source_id"]}
    triage = Triage.model_validate(state["triage"])
    verified = set(triage.evidence_ids) == required
    if MODE != "replay":
        verified = verified and {"lookup_demo_bill", "get_demo_policy"}.issubset(
            state["tool_calls"]
        )
    if not verified:
        triage.needs_specialist = True
        triage.draft_response = "The evidence references could not be verified. Staff must review this request."
    if triage.category != "balance" or not bill.get("found", True):
        triage.needs_specialist = True
    return {
        "triage": triage.model_dump(),
        "evidence_verified": verified,
        "status": "awaiting_review",
    }


def wait_for_human(state: GraphState) -> dict:
    payload = {
        "type": "billing_draft_review",
        "bill_id": state["bill_id"],
        "triage": state["triage"],
        "evidence_verified": state["evidence_verified"],
        "allowed_decisions": ["approve", "reject"],
        "sends_message": False,
    }
    if os.getenv("UIPATH_REVIEW_APP"):
        from uipath.platform.common import CreateTask

        payload = CreateTask(
            app_name=os.environ["UIPATH_REVIEW_APP"],
            title="Review synthetic billing draft",
            app_version=1,
            app_folder_path=os.environ["UIPATH_REVIEW_FOLDER"],
            data={
                "AgentOutput": json.dumps(payload),
                "AgentName": "revenue-cycle-agent",
            },
        )
    decision = ReviewDecision.model_validate(interrupt(payload))
    # Approval records readiness only; no sending or billing-write tools exist.
    return {
        "review": decision.model_dump(),
        "status": "reviewed_draft" if decision.decision == "approve" else "rejected",
    }


def build_graph(checkpointer=None):
    builder = StateGraph(GraphState, input_schema=GraphInput, output_schema=GraphOutput)
    builder.add_node("classify", classify)
    builder.add_node("verify_evidence", verify_evidence)
    builder.add_node("human_review", wait_for_human)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "verify_evidence")
    builder.add_edge("verify_evidence", "human_review")
    builder.add_edge("human_review", END)
    return builder.compile(checkpointer=checkpointer)


# UiPath supplies its runtime checkpointing; local demo uses process memory.
graph = build_graph()
demo_graph = build_graph(MemorySaver())
