"""
AfriMine AI — A2A Bridge (JSON-RPC 2.0 Server)
=================================================

Exposes the LangGraph pipeline as an A2A-compatible agent via FastAPI.

Endpoints:
    GET  /.well-known/agent.json  — Agent Card discovery
    POST /a2a                     — JSON-RPC 2.0 tasks/send & tasks/send_stream
    GET  /health                  — Health check

Usage:
    uvicorn a2a_bridge:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from config import settings
from main import AfriMinePipeline

logger = logging.getLogger("afrimine.a2a_bridge")

app = FastAPI(title="AfriMine A2A Bridge", version="1.0.0")

# Lazy pipeline singleton — created on first request
_pipeline: AfriMinePipeline | None = None


def _get_pipeline() -> AfriMinePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AfriMinePipeline(use_memory_checkpointer=True)
        logger.info("AfriMine pipeline initialized")
    return _pipeline


# ---------------------------------------------------------------------------
# Agent Card (A2A discovery)
# ---------------------------------------------------------------------------

AGENT_CARD = {
    "name": "afrimine-pipeline",
    "description": "AfriMine AI — 6-agent mineral analysis pipeline for artisanal mining sites in Kenya",
    "version": "1.0.0",
    "url": "http://localhost:8000",
    "capabilities": {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    },
    "authentication": {
        "schemes": ["bearer"],
    },
    "defaultInputModes": ["text", "data"],
    "defaultOutputModes": ["text", "data"],
    "skills": [
        {
            "id": "mineral-analysis",
            "name": "Mineral Analysis Pipeline",
            "description": "Complete 6-agent analysis: Sampling → Analysis → Geology/Market → Report → Compliance",
            "tags": ["mining", "geology", "compliance", "kenya"],
            "examples": [
                "Analyze this mineral sample from Nyatike, Migori County",
                "Check compliance for a gold sample with 5.2 g/t grade",
            ],
        }
    ],
}


@app.get("/.well-known/agent.json")
async def agent_card():
    """A2A Agent Card discovery endpoint."""
    return JSONResponse(content=AGENT_CARD)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "afrimine-a2a-bridge",
        "pipeline": "langgraph",
        "agents": [
            "sampling", "analysis", "geology", "market", "report", "compliance"
        ],
    }


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 dispatcher
# ---------------------------------------------------------------------------

@app.post("/a2a")
@app.post("/a2a/{agent_id}")
async def a2a_endpoint(request: Request, agent_id: str = "afrimine-pipeline"):
    """Main A2A JSON-RPC 2.0 endpoint."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
        )

    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id", str(uuid.uuid4()))

    logger.info("A2A request: method=%s agent=%s id=%s", method, agent_id, req_id)

    if method == "tasks/send":
        return await _handle_tasks_send(params, req_id)
    elif method == "tasks/send_stream":
        return await _handle_tasks_send_stream(params, req_id)
    elif method == "tasks/get":
        return await _handle_tasks_get(params, req_id)
    else:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": req_id,
            }
        )


# ---------------------------------------------------------------------------
# tasks/send — synchronous pipeline execution
# ---------------------------------------------------------------------------

async def _handle_tasks_send(params: dict, req_id: str) -> JSONResponse:
    """Handle tasks/send — run the full pipeline and return result."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])

    # Extract input from message parts
    input_data = _extract_input(parts)
    if not input_data:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Invalid params: missing location/sample_data"},
                "id": req_id,
            }
        )

    start_time = time.time()

    try:
        pipeline = _get_pipeline()
        result = await pipeline.analyze(
            location=input_data.get("location", {}),
            sample_data=input_data.get("sample_data", {}),
            user_id=input_data.get("user_id", "a2a-user"),
            analysis_id=task_id,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info("Pipeline completed: task=%s duration=%dms", task_id, duration_ms)

        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "status": {"state": "completed", "message": f"Analysis complete in {duration_ms}ms"},
                    "artifacts": [
                        {
                            "parts": [
                                {
                                    "type": "data",
                                    "data": _sanitize_for_json(result),
                                    "mimeType": "application/json",
                                },
                                {
                                    "type": "text",
                                    "text": _build_summary(result),
                                },
                            ]
                        }
                    ],
                },
            }
        )

    except ValueError as e:
        logger.warning("Validation error: %s", e)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "status": {"state": "failed", "message": str(e)},
                },
            }
        )
    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "status": {"state": "failed", "message": f"Pipeline error: {type(e).__name__}: {e}"},
                },
            }
        )


# ---------------------------------------------------------------------------
# tasks/send_stream — SSE streaming pipeline execution
# ---------------------------------------------------------------------------

async def _handle_tasks_send_stream(params: dict, req_id: str):
    """Handle tasks/send_stream — stream pipeline progress via SSE."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    parts = message.get("parts", [])

    input_data = _extract_input(parts)
    if not input_data:
        async def error_stream():
            yield f"data: {json.dumps({'id': task_id, 'status': 'failed', 'output': {'error': 'Invalid params'}})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    async def stream_generator():
        """Generate SSE events as agents complete."""
        # Initial event
        yield f"data: {json.dumps({'id': task_id, 'status': 'working', 'node': 'start', 'output': {'agent': 'pipeline', 'status': 'started'}})}\n\n"

        try:
            pipeline = _get_pipeline()

            async for node_name, partial_state in pipeline.stream(
                location=input_data.get("location", {}),
                sample_data=input_data.get("sample_data", {}),
                user_id=input_data.get("user_id", "a2a-user"),
                analysis_id=task_id,
            ):
                event_data = {
                    "id": task_id,
                    "status": "working",
                    "node": node_name,
                    "output": {
                        "agent": node_name,
                        "status": "completed",
                    },
                }

                # Include key results from each node
                if node_name == "analysis" and partial_state.get("analysis_result"):
                    ar = partial_state["analysis_result"]
                    event_data["output"]["dominant_mineral"] = ar.get("dominant_mineral", "")
                    event_data["output"]["confidence"] = str(ar.get("overall_confidence", 0))
                elif node_name == "market" and partial_state.get("market_result"):
                    mr = partial_state["market_result"]
                    event_data["output"]["gold_price"] = str(mr.get("gold_price_usd_oz", 0))
                    event_data["output"]["deposit_value"] = str(mr.get("deposit_value_estimate_usd", 0))
                elif node_name == "compliance" and partial_state.get("compliance_result"):
                    cr = partial_state["compliance_result"]
                    event_data["output"]["compliant"] = str(cr.get("is_compliant", False))

                # Include errors if any
                errors = partial_state.get("errors", [])
                if errors:
                    event_data["output"]["errors"] = json.dumps(errors)

                yield f"data: {json.dumps(event_data)}\n\n"

            # Final completion event
            yield f"data: {json.dumps({'id': task_id, 'status': 'completed', 'node': 'end', 'output': {'agent': 'pipeline', 'status': 'completed'}})}\n\n"

        except Exception as e:
            logger.error("Stream pipeline failed: %s", e, exc_info=True)
            yield f"data: {json.dumps({'id': task_id, 'status': 'failed', 'node': 'error', 'output': {'error': str(e)}})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# tasks/get — retrieve task status (stub for future use)
# ---------------------------------------------------------------------------

async def _handle_tasks_get(params: dict, req_id: str) -> JSONResponse:
    """Handle tasks/get — return task status (in-memory for now)."""
    task_id = params.get("id", "")
    return JSONResponse(
        content={
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "id": task_id,
                "status": {"state": "unknown", "message": "Task history not yet persisted"},
            },
        }
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_input(parts: list[dict]) -> dict[str, Any]:
    """Extract location/sample_data/user_id from A2A message parts."""
    result: dict[str, Any] = {}

    for part in parts:
        if part.get("type") == "data" and isinstance(part.get("data"), dict):
            data = part["data"]
            if "location" in data:
                result["location"] = data["location"]
            if "sample_data" in data:
                result["sample_data"] = data["sample_data"]
            if "user_id" in data:
                result["user_id"] = data["user_id"]
            if "satellite_imagery" in data:
                result["satellite_imagery"] = data["satellite_imagery"]

    return result


def _sanitize_for_json(obj: Any) -> Any:
    """Make state dict JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)


def _build_summary(result: dict[str, Any]) -> str:
    """Build a human-readable summary of the analysis result."""
    parts = []

    compliance = result.get("compliance_result", {})
    market = result.get("market_result", {})
    analysis = result.get("analysis_result", {})
    report = result.get("report_result", {})

    if analysis.get("dominant_mineral"):
        parts.append(f"Mineral: {analysis['dominant_mineral']} ({analysis.get('overall_confidence', 0):.0%} confidence)")

    if market.get("gold_price_usd_oz"):
        parts.append(f"Gold: ${market['gold_price_usd_oz']:,.0f}/oz")

    if market.get("deposit_value_estimate_usd"):
        parts.append(f"Deposit value: ${market['deposit_value_estimate_usd']:,.0f} NPV")

    if compliance.get("is_compliant") is not None:
        status = "✅ Compliant" if compliance["is_compliant"] else "⚠️ Non-compliant"
        parts.append(status)

    if report.get("recommendation"):
        parts.append(f"Recommendation: {report['recommendation']}")

    return " | ".join(parts) if parts else "Analysis completed"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
