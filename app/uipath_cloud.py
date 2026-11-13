"""UiPath cloud orchestration around the live Google Cloud cost agent.

The complete evidence snapshot lives in UiPath graph state during review; it
does not depend on the browser demo's short-lived, in-memory session surviving.
"""

import json
from typing import Literal, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from uipath.platform import UiPath
from uipath.platform.action_center.tasks import Task
from uipath.platform.common import UiPathConfig, WaitTask

DEMO_URL = "https://revenue-cycle-agent-1038659864130.us-central1.run.app"
SCHEMA_ID = "88e922bb-61d1-4d20-9776-03c2a62cb895"
FORM_SCHEMA = {
    "schemaId": SCHEMA_ID,
    "fields": [
        {"id": "question", "label": "Inquiry", "type": "string", "direction": "input"},
        {
            "id": "evidence",
            "label": "CMS evidence and checks",
            "type": "string",
            "direction": "input",
        },
        {
            "id": "response",
            "label": "Review and edit the draft",
            "type": "string",
            "direction": "inOut",
            "required": True,
        },
        {
            "id": "comment",
            "label": "Reviewer note",
            "type": "string",
            "direction": "output",
        },
    ],
    "outcomes": [
        {
            "id": "approve",
            "name": "Approve draft",
            "type": "string",
            "isPrimary": True,
            "action": "Continue",
        },
        {
            "id": "reject",
            "name": "Return for review",
            "type": "string",
            "isPrimary": False,
            "action": "End",
        },
    ],
}


class CloudInput(BaseModel):
    case_id: Literal[
        "explain", "benchmark", "personal", "dispute", "unavailable", "missing"
    ] = "explain"


class CloudState(TypedDict, total=False):
    case_id: str
    evidence_snapshot: dict
    action_task: dict
    review: dict
    approved_response: str | None
    status: str


class CloudOutput(BaseModel):
    evidence_snapshot: dict = Field(default_factory=dict)
    action_task: dict = Field(default_factory=dict)
    review: dict = Field(default_factory=dict)
    approved_response: str | None = None
    status: str = "pending"


async def call_cloud_agent(state: CloudState) -> dict:
    request = CloudInput.model_validate(state)
    async with httpx.AsyncClient(timeout=210) as client:
        response = await client.post(
            f"{DEMO_URL}/api/investigate", json=request.model_dump()
        )
        response.raise_for_status()
        snapshot = response.json()
    if snapshot.get("status") != "awaiting_review" or not snapshot.get("tool_trace"):
        raise ValueError("The live agent did not return an evidence-backed draft.")
    return {"evidence_snapshot": snapshot, "status": "creating_review"}


async def create_review_task(state: CloudState) -> dict:
    snapshot = state["evidence_snapshot"]
    task = await UiPath().tasks.create_quickform_async(
        title=f"CMS cost inquiry — {state.get('case_id', 'explain')}",
        task_schema_key=SCHEMA_ID,
        schema=FORM_SCHEMA,
        folder_key=UiPathConfig.folder_key,
        data={
            "question": snapshot["question"],
            "response": snapshot["draft"]["response"],
            "evidence": json.dumps(
                {
                    "data_scope": "2024 public hospital/service averages; not a patient bill",
                    "tool_trace": snapshot["tool_trace"],
                    "checks": snapshot["checks"],
                    "routing": snapshot["routing"],
                    "sends_message": False,
                },
                indent=2,
            ),
        },
        is_actionable_message_enabled=False,
    )
    return {"action_task": task.model_dump(mode="json"), "status": "awaiting_review"}


def finish_review(snapshot: dict, completed: Task) -> dict:
    if completed.is_deleted:
        return {
            "status": "review_deleted",
            "approved_response": None,
            "review": {"decision": "deleted"},
        }
    if completed.status != 2:
        raise ValueError("The Action Center task is not completed.")
    decision = (completed.action or "").lower()
    if decision not in {"approve", "reject"}:
        raise ValueError(f"Unrecognized review outcome: {decision!r}")
    data = completed.data or {}
    edited = data.get("response")
    if edited is not None and (
        not isinstance(edited, str) or not edited.strip() or len(edited) > 2000
    ):
        raise ValueError(
            "The reviewed response must be nonempty text up to 2000 characters."
        )
    return {
        "review": {
            "decision": decision,
            "comment": data.get("comment", ""),
            "task_id": completed.id,
        },
        "approved_response": (edited or snapshot["draft"]["response"])
        if decision == "approve"
        else None,
        "status": "reviewed_draft" if decision == "approve" else "rejected",
    }


async def wait_for_reviewer(state: CloudState) -> dict:
    task = Task.model_validate(state["action_task"])
    interrupt(WaitTask(action=task, app_folder_key=UiPathConfig.folder_key))
    # Cloud resume payload shape differs by runtime. The completed Action Center
    # record is authoritative; never treat an arbitrary resume signal as approval.
    completed = await UiPath().tasks.retrieve_async(
        task.key, app_folder_key=UiPathConfig.folder_key
    )
    return finish_review(state["evidence_snapshot"], completed)


def build_cloud_graph(checkpointer=None):
    builder = StateGraph(CloudState, input_schema=CloudInput, output_schema=CloudOutput)
    builder.add_node("call_vertex_agent", call_cloud_agent)
    builder.add_node("create_action_center_review", create_review_task)
    builder.add_node("wait_for_human", wait_for_reviewer)
    builder.add_edge(START, "call_vertex_agent")
    builder.add_edge("call_vertex_agent", "create_action_center_review")
    builder.add_edge("create_action_center_review", "wait_for_human")
    builder.add_edge("wait_for_human", END)
    return builder.compile(checkpointer=checkpointer)


graph = build_cloud_graph()
