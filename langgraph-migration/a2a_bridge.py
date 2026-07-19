"""
AfriMine AI — A2A Protocol Bridge (Go ↔ Python)
==================================================

Implements Google's Agent-to-Agent (A2A) protocol for cross-language
communication between the Go backend and Python LangGraph agents.

Protocol: JSON-RPC 2.0 over HTTP
Discovery: Agent Cards at /.well-known/agent.json
Endpoints: /a2a (unified RPC endpoint)

Architecture:
    Go Backend ──HTTP POST /a2a──→ FastAPI ──→ LangGraph agents
                   JSON-RPC 2.0        │
                                       ├─ tasks/send      → run pipeline
                                       ├─ tasks/send_stream → stream pipeline
                                       └─ tasks/get       → get result by ID

Why A2A (not gRPC):
- Language-agnostic: Go, Python, Dart all speak JSON-RPC
- Simple: no .proto files, no code generation
- Google-standard: 150+ organizations in the A2A ecosystem
- Debuggable: plain JSON over HTTP — curl-friendly
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# A2A Agent Card — metadata for agent discovery
# ---------------------------------------------------------------------------

AGENT_CARDS = {
    "afrimine-pipeline": {
        "name": "AfriMine AI Pipeline",
        "description": "Complete 6-agent mineral analysis pipeline: Sampling → Analysis → Geology/Market → Report → Compliance",
        "url": "http://localhost:8000/a2a",
        "version": "2.0.0",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text", "data"],
        "defaultOutputModes": ["text", "data"],
        "skills": [
            {
                "id": "mineral-analysis",
                "name": "Mineral Analysis",
                "description": "Full pipeline: classify minerals, interpret geology, value deposit, check compliance",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                                "region": {"type": "string"},
                                "county": {"type": "string"},
                            },
                            "required": ["lat", "lon"],
                        },
                        "sample_data": {
                            "type": "object",
                            "properties": {
                                "sample_id": {"type": "string"},
                                "photo_url": {"type": "string"},
                                "xrf_readings": {"type": "object"},
                                "notes": {"type": "string"},
                            },
                        },
                    },
                    "required": ["location"],
                },
            }
        ],
    },
    "sampling": {
        "name": "AfriMine Sampling Agent",
        "description": "GPS waypoint generation and field route optimization",
        "url": "http://localhost:8000/a2a/sampling",
        "version": "2.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["data"],
        "defaultOutputModes": ["data"],
        "skills": [{"id": "waypoint-generation", "name": "Waypoint Generation"}],
    },
    "analysis": {
        "name": "AfriMine Analysis Agent",
        "description": "Mineral classification using Gemini 2.5 Flash vision",
        "url": "http://localhost:8000/a2a/analysis",
        "version": "2.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text", "image", "data"],
        "defaultOutputModes": ["data"],
        "skills": [{"id": "mineral-classification", "name": "Mineral Classification"}],
    },
    "geology": {
        "name": "AfriMine Geology Agent",
        "description": "Geological context interpretation for Migori Belt",
        "url": "http://localhost:8000/a2a/geology",
        "version": "2.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["data"],
        "defaultOutputModes": ["data"],
        "skills": [{"id": "deposit-modeling", "name": "Deposit Modeling"}],
    },
    "market": {
        "name": "AfriMine Market Agent",
        "description": "Commodity prices and deposit valuation",
        "url": "http://localhost:8000/a2a/market",
        "version": "2.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["data"],
        "defaultOutputModes": ["data"],
        "skills": [{"id": "deposit-valuation", "name": "Deposit Valuation"}],
    },
    "report": {
        "name": "AfriMine Report Agent",
        "description": "Investor-ready report generation",
        "url": "http://localhost:8000/a2a/report",
        "version": "2.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["data"],
        "defaultOutputModes": ["text", "data"],
        "skills": [{"id": "report-generation", "name": "Report Generation"}],
    },
    "compliance": {
        "name": "AfriMine Compliance Agent",
        "description": "Kenya Mining Act 2016 compliance checking",
        "url": "http://localhost:8000/a2a/compliance",
        "version": "2.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["data"],
        "defaultOutputModes": ["data"],
        "skills": [{"id": "compliance-check", "name": "Compliance Check"}],
    },
}


# ---------------------------------------------------------------------------
# Task store (in-memory for MVP; use Supabase in production)
# ---------------------------------------------------------------------------

_task_store: dict[str, dict[str, Any]] = {}


def _store_task(task_id: str, data: dict[str, Any]) -> None:
    """Store task state for retrieval."""
    _task_store[task_id] = data


def _get_task(task_id: str) -> dict[str, Any] | None:
    """Retrieve task state by ID."""
    return _task_store.get(task_id)


# ---------------------------------------------------------------------------
# A2A Protocol Handlers
# ---------------------------------------------------------------------------

async def _handle_send(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle A2A tasks/send — run the full pipeline synchronously.

    A2A request format:
    {
        "method": "tasks/send",
        "params": {
            "id": "task-001",
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "..."}, {"type": "data", "data": {...}}]
            }
        }
    }
    """
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])

    # Extract data from message parts
    input_data: dict[str, Any] = {}
    for part in parts:
        if part.get("type") == "data":
            input_data.update(part.get("data", {}))
        elif part.get("type") == "text":
            input_data.setdefault("notes", part.get("text", ""))

    if not input_data.get("location"):
        return {
            "id": task_id,
            "status": {"state": "failed", "message": "Missing required 'location' field"},
        }

    # Run the pipeline
    try:
        from checkpointer import get_checkpointer
        from graph import run_analysis

        checkpointer = get_checkpointer(use_memory=True)  # Production: use Supabase

        initial_state = {
            "location": input_data.get("location", {}),
            "sample_data": input_data.get("sample_data", {}),
            "satellite_imagery": input_data.get("satellite_imagery", ""),
            "user_id": input_data.get("user_id", "a2a-client"),
            "analysis_id": task_id,
            "messages": [],
            "errors": [],
            "metadata": {"source": "a2a", "protocol": "json-rpc-2.0"},
            "refinement_count": 0,
        }

        result = await run_analysis(initial_state, checkpointer=checkpointer)

        # Format A2A response
        response_text = (
            f"Analysis complete.\n"
            f"Mineral: {result.get('analysis_result', {}).get('dominant_mineral', 'unknown')}\n"
            f"Value: ${result.get('market_result', {}).get('deposit_value_estimate_usd', 0):,.0f}\n"
            f"Compliant: {result.get('compliance_result', {}).get('is_compliant', False)}"
        )

        task_result = {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "parts": [
                        {"type": "text", "text": response_text},
                        {"type": "data", "data": result},
                    ]
                }
            ],
        }

        _store_task(task_id, task_result)
        return task_result

    except Exception as e:
        logger.error(f"A2A task {task_id} failed: {e}", exc_info=True)
        return {
            "id": task_id,
            "status": {"state": "failed", "message": str(e)},
        }


async def _handle_send_stream(params: dict[str, Any]):
    """
    Handle A2A tasks/send_stream — stream pipeline progress via SSE.

    Same input as tasks/send, but yields events as each agent completes.
    """
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])

    input_data: dict[str, Any] = {}
    for part in parts:
        if part.get("type") == "data":
            input_data.update(part.get("data", {}))
        elif part.get("type") == "text":
            input_data.setdefault("notes", part.get("text", ""))

    from checkpointer import get_checkpointer
    from graph import stream_analysis

    checkpointer = get_checkpointer(use_memory=True)

    initial_state = {
        "location": input_data.get("location", {}),
        "sample_data": input_data.get("sample_data", {}),
        "satellite_imagery": input_data.get("satellite_imagery", ""),
        "user_id": input_data.get("user_id", "a2a-client"),
        "analysis_id": task_id,
        "messages": [],
        "errors": [],
        "metadata": {"source": "a2a-stream"},
        "refinement_count": 0,
    }

    async def event_generator():
        """Generate SSE events for each agent completion."""
        async for node_name, node_output in stream_analysis(initial_state, checkpointer=checkpointer):
            event_data = {
                "id": task_id,
                "status": {"state": "working"},
                "node": node_name,
                "output": {k: v for k, v in node_output.items() if k != "messages"},
            }
            yield f"data: {json.dumps(event_data)}\n\n"

        # Final event
        yield f"data: {json.dumps({'id': task_id, 'status': {'state': 'completed'}})}\n\n"

    return event_generator()


async def _handle_get(params: dict[str, Any]) -> dict[str, Any]:
    """Handle A2A tasks/get — retrieve a completed task by ID."""
    task_id = params.get("id")
    task = _get_task(task_id)

    if task is None:
        return {
            "id": task_id,
            "status": {"state": "unknown", "message": f"Task {task_id} not found"},
        }

    return task


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create the A2A bridge FastAPI application."""
    app = FastAPI(
        title="AfriMine AI — A2A Bridge",
        description="Agent-to-Agent protocol bridge for Go ↔ Python communication",
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production: restrict to Go backend origin
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Agent Card Discovery ───────────────────────────────────────────

    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """Return the primary pipeline agent card for A2A discovery."""
        return AGENT_CARDS["afrimine-pipeline"]

    @app.get("/.well-known/agent/{agent_id}.json")
    async def get_specific_agent_card(agent_id: str):
        """Return a specific agent's card."""
        card = AGENT_CARDS.get(agent_id)
        if not card:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return card

    @app.get("/agents")
    async def list_agents():
        """List all available agent cards."""
        return {"agents": list(AGENT_CARDS.values())}

    # ── A2A JSON-RPC Endpoint ──────────────────────────────────────────

    @app.post("/a2a")
    async def a2a_endpoint(request: Request):
        """
        Unified A2A JSON-RPC 2.0 endpoint.

        Supports methods:
        - tasks/send       → run full pipeline synchronously
        - tasks/send_stream → stream pipeline progress (SSE)
        - tasks/get        → retrieve task by ID
        """
        body = await request.json()
        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id")

        logger.info(f"A2A request: method={method}, id={req_id}")

        if method == "tasks/send":
            result = await _handle_send(params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        elif method == "tasks/send_stream":
            event_gen = await _handle_send_stream(params)
            return StreamingResponse(event_gen, media_type="text/event-stream")

        elif method == "tasks/get":
            result = await _handle_get(params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    # ── Health Check ───────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "afrimine-a2a-bridge", "version": "2.0.0"}

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
