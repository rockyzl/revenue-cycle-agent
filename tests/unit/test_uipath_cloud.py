from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from uipath.platform.action_center.tasks import Task

from app import uipath_cloud as cloud


@pytest.mark.asyncio
async def test_cloud_review_resumes_without_repeating_live_call(monkeypatch):
    calls = []
    snapshot = {
        "draft": {"response": "Original CMS draft"},
        "tool_trace": [{"source": "CMS"}],
    }

    async def investigate(state):
        calls.append("live")
        return {"evidence_snapshot": snapshot}

    async def create(state):
        calls.append("task")
        return {
            "action_task": {"id": 1, "key": "review-1"},
            "status": "awaiting_review",
        }

    async def retrieve(key, **kwargs):
        assert key == "review-1"
        return Task(
            id=1, status=2, action="approve", data={"response": "Reviewer edit"}
        )

    monkeypatch.setattr(
        cloud,
        "UiPath",
        lambda: SimpleNamespace(tasks=SimpleNamespace(retrieve_async=retrieve)),
    )
    monkeypatch.setattr(cloud, "call_cloud_agent", investigate)
    monkeypatch.setattr(cloud, "create_review_task", create)
    graph = cloud.build_cloud_graph(MemorySaver())
    config = {"configurable": {"thread_id": "cloud-review"}}
    await graph.ainvoke({"case_id": "personal"}, config)
    assert (await graph.aget_state(config)).next == ("wait_for_human",)
    result = await graph.ainvoke(
        Command(
            resume={"id": 1, "action": "approve", "data": {"response": "Reviewer edit"}}
        ),
        config,
    )
    assert calls == ["live", "task"]
    assert result["approved_response"] == "Reviewer edit"
    assert result["evidence_snapshot"]["draft"]["response"] == "Original CMS draft"


def test_reject_deleted_and_unknown_never_approve():
    snapshot = {"draft": {"response": "Draft"}}
    for task in [Task(action="reject", status=2), Task(is_deleted=True)]:
        assert cloud.finish_review(snapshot, task)["approved_response"] is None
    with pytest.raises(ValueError):
        cloud.finish_review(snapshot, Task(action="unknown", status=2))


def test_incomplete_task_cannot_approve():
    with pytest.raises(ValueError, match="not completed"):
        cloud.finish_review(
            {"draft": {"response": "Draft"}}, Task(action="approve", status=1)
        )
