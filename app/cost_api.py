"""Bounded public demo API; model calls accept only published sample cases."""

import asyncio
import time
from collections import defaultdict, deque
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict

from app.agent import LLM, MODE
from app.cms import DATA_YEAR, DATASET_PAGE
from app.cost_workflow import CostInput, CostReview, web_graph

CASES = [
    {
        "id": "explain",
        "title": "Explain the three amounts",
        "apc_code": "5072",
        "question": "Explain the difference between submitted charges, allowed amount and Medicare payment for this service.",
    },
    {
        "id": "benchmark",
        "title": "Look up a service benchmark",
        "apc_code": "5113",
        "question": "What historical cost information does CMS report for this hospital and service?",
    },
    {
        "id": "personal",
        "title": "Can you estimate my payment?",
        "apc_code": "5072",
        "question": "Can you tell me exactly how much I personally will owe after Medicare?",
    },
    {
        "id": "dispute",
        "title": "Question a higher charge",
        "apc_code": "5073",
        "question": "My bill seems higher than this benchmark. Does that prove an incorrect charge, and what should I gather for staff review?",
    },
    {
        "id": "unavailable",
        "title": "Handle an unavailable amount",
        "apc_code": "5200",
        "question": "What does CMS report for this service? If an amount is blank, does that mean the service is free?",
    },
    {
        "id": "missing",
        "title": "Handle a missing service",
        "apc_code": "0000",
        "question": "Find the historical costs for this provider and service code, and explain what to do if there is no row.",
    },
]
for case in CASES:
    case["provider_ccn"] = "240010"
    case["provider"] = "Mayo Clinic Hospital Rochester"

router = APIRouter(prefix="/api")
_sessions: dict[str, asyncio.Lock] = {}
_recent: dict[str, deque] = defaultdict(deque)
_gate = asyncio.Semaphore(2)


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str


@router.get("/config")
def config():
    return {
        "mode": MODE,
        "model": LLM,
        "data_year": DATA_YEAR,
        "dataset_url": DATASET_PAGE,
        "cases": CASES,
        "uipath_cloud": "Not connected; developer account setup pending",
    }


async def view(session_id):
    snapshot = await web_graph.aget_state({"configurable": {"thread_id": session_id}})
    return {
        "session_id": session_id,
        **snapshot.values,
        "paused": bool(snapshot.next),
        "runtime": {
            "mode": MODE,
            "model": LLM,
            "data": "Live CMS API",
            "orchestration": "LangGraph",
        },
    }


@router.post("/investigate")
async def investigate(body: CaseRequest, request: Request):
    case = next((c for c in CASES if c["id"] == body.case_id), None)
    if not case:
        raise HTTPException(422, "Choose one of the available demo cases.")
    if MODE not in {"vertex", "uipath"}:
        raise HTTPException(
            503,
            "Start the server with BILLING_MODE=vertex and Google Cloud credentials.",
        )
    if len(_sessions) >= 100:
        raise HTTPException(429, "This demo instance has reached its session limit.")
    host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = _recent[host]
    while recent and recent[0] < now - 600:
        recent.popleft()
    if len(recent) >= 6:
        raise HTTPException(
            429, "Six live runs per ten minutes. Please return shortly."
        )
    recent.append(now)
    session_id = uuid4().hex
    _sessions[session_id] = asyncio.Lock()
    input_data = CostInput.model_validate(
        {k: case[k] for k in ("question", "provider_ccn", "apc_code")}
    )
    try:
        async with _gate:
            await asyncio.wait_for(
                web_graph.ainvoke(
                    input_data.model_dump(), {"configurable": {"thread_id": session_id}}
                ),
                timeout=180,
            )
        return await view(session_id)
    except Exception as exc:
        _sessions.pop(session_id, None)
        # Never replace failed live retrieval/inference with a fabricated answer.
        raise HTTPException(
            502, "The live data or model request failed. Retry this case in a moment."
        ) from exc


@router.post("/sessions/{session_id}/review")
async def review(session_id: str, body: CostReview):
    if session_id not in _sessions:
        raise HTTPException(404, "Session expired. Run the case again.")
    async with _sessions[session_id]:
        state = await view(session_id)
        if not state["paused"]:
            raise HTTPException(409, "This draft has already been reviewed.")
        await web_graph.ainvoke(
            Command(resume=body.model_dump()),
            {"configurable": {"thread_id": session_id}},
        )
        return await view(session_id)
