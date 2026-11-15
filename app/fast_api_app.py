# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""FastAPI app serving the agent over the A2A protocol.

The agent is exposed through the Agent2Agent (A2A) JSON-RPC surface at
``/a2a/{name}``, with its Agent Card at the well-known path. This mirrors the
contract used by agents-cli's ADK A2A agents, so the deploy entrypoint
(``uvicorn app.fast_api_app:app``) and ``agents-cli run --mode a2a`` keep
working unchanged.

For the richest *local* LangGraph experience (graph inspection, streaming,
threads), ``agents-cli playground`` runs ``langgraph dev``, which also serves
the A2A protocol natively.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command

from app.agent import MODE
from app.app_utils.a2a import add_a2a_routes
from app.app_utils.telemetry import setup_telemetry
from app.cost_api import router as cost_router
from app.portal.api import router as portal_router
from app.integration_api import router as integration_router
from app.workflow import GraphInput, ReviewDecision, demo_graph

# Optional upstream telemetry; off for this small local prototype. The current
# LangChain instrumentor does not implement the LangGraph interrupt callback.
if os.getenv("BILLING_ENABLE_TELEMETRY", "false").lower() == "true":
    setup_telemetry()


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    if os.getenv("PUBLIC_DEMO") != "true":
        add_a2a_routes(app_instance)
    yield


app = FastAPI(
    title="Billing Inbox Agent",
    description="Synthetic billing draft and human-review prototype",
    lifespan=lifespan,
)
app.include_router(cost_router)
app.include_router(portal_router)
app.include_router(integration_router)


@app.middleware("http")
async def private_portal_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/portal/api'):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response

app.mount(
    "/assets",
    StaticFiles(directory=Path(__file__).parent / "static" / "assets"),
    name="assets",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": MODE,
        "data": "CMS public aggregates",
        "uipath_cloud": "separate_cloud_workflow",
    }


_sessions: dict[str, asyncio.Lock] = {}


@app.get("/", response_class=HTMLResponse)
def demo_page():
    return (Path(__file__).parent / "static" / "home.html").read_text()


@app.get("/billing", response_class=HTMLResponse)
def billing_page():
    return (Path(__file__).parent / "static" / "portal.html").read_text()


@app.get("/integration", response_class=HTMLResponse)
def integration_page():
    return (Path(__file__).parent / "static" / "integration.html").read_text()


@app.get("/cms", response_class=HTMLResponse)
def cms_page():
    return (Path(__file__).parent / "static" / "index.html").read_text()


async def _view(session_id: str):
    snapshot = await demo_graph.aget_state({"configurable": {"thread_id": session_id}})
    return {"session_id": session_id, **snapshot.values, "paused": bool(snapshot.next)}


@app.post("/demo/run")
async def start_demo(request: GraphInput):
    if os.getenv("PUBLIC_DEMO") == "true":
        raise HTTPException(404, "Legacy fixture API is disabled in the public demo.")
    if len(_sessions) >= 100:
        raise HTTPException(
            429, "Demo session limit reached; restart the demo to clear it."
        )
    session_id = uuid4().hex
    _sessions[session_id] = asyncio.Lock()
    try:
        await demo_graph.ainvoke(
            request.model_dump(), {"configurable": {"thread_id": session_id}}
        )
        return await _view(session_id)
    except Exception as exc:
        _sessions.pop(session_id, None)
        logging.getLogger(__name__).error(
            "Demo invocation failed: %s", type(exc).__name__
        )
        raise HTTPException(
            502, "Agent invocation failed; check local/cloud logs."
        ) from exc


@app.post("/demo/{session_id}/review")
async def review_demo(session_id: str, decision: ReviewDecision):
    if os.getenv("PUBLIC_DEMO") == "true":
        raise HTTPException(404, "Legacy fixture API is disabled in the public demo.")
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found; sessions reset on restart.")
    async with _sessions[session_id]:
        view = await _view(session_id)
        if not view["paused"]:
            raise HTTPException(409, "This draft has already been reviewed.")
        await demo_graph.ainvoke(
            Command(resume=decision.model_dump()),
            {"configurable": {"thread_id": session_id}},
        )
        return await _view(session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
    )
