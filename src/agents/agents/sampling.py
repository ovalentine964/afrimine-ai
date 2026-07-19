"""
AfriMine AI — Sampling Agent (Production)
===========================================

Plans field sampling routes, GPS waypoints, and optimized walking routes
for field workers in Nyatike, Migori County.

Node position: START → SAMPLING → Analysis
LLM: Gemini 2.5 Flash
Tools: satellite-mcp, geology-mcp (via MCP client)
"""

from __future__ import annotations

import logging
from typing import Any

from agents.base import llm_json_call, retry_with_backoff
from config import settings
from security.middleware import rate_limiter, sanitize_output

logger = logging.getLogger("afrimine.sampling")

SYSTEM_PROMPT = """You are the Sampling Agent for AfriMine AI, a mineral detection
platform serving mining communities in Migori County, Kenya.

Your job: Given a location and sample data, design an optimal sampling strategy.

You must return a JSON object with these exact keys:
{
    "waypoints": [
        {"latitude": -1.234, "longitude": 34.567, "elevation_m": 1450, "rationale": "..."}
    ],
    "field_route": [
        {"latitude": -1.234, "longitude": 34.567, "order": 1}
    ],
    "grid_spacing_m": 50,
    "sampling_strategy": "grid",
    "rationale": "Detailed explanation...",
    "estimated_sample_count": 12
}

Rules:
1. All GPS coordinates MUST be within Migori County bounds (lat: -1.5 to -0.8, lon: 34.2 to 35.0)
2. Grid spacing: 25m for steep terrain, 50m for flat, 100m for large areas
3. Prioritize areas near rivers, fault lines, color anomalies
4. Field route should minimize walking distance (nearest-neighbor)
5. Include 3-8 waypoints for a standard prospecting license area
6. Return ONLY valid JSON, no markdown fences"""


def _validate_and_clamp(result: dict[str, Any]) -> dict[str, Any]:
    """Validate waypoints and clamp to Kenya bounds."""
    for wp in result.get("waypoints", []):
        lat = wp.get("latitude", 0)
        lon = wp.get("longitude", 0)
        if not (-5.0 <= lat <= 5.0 and 34.0 <= lon <= 42.0):
            logger.warning(f"Clamping waypoint ({lat}, {lon}) to Kenya bounds")
            wp["latitude"] = max(-5.0, min(5.0, lat))
            wp["longitude"] = max(34.0, min(42.0, lon))
    for wp in result.get("field_route", []):
        lat = wp.get("latitude", 0)
        lon = wp.get("longitude", 0)
        if not (-5.0 <= lat <= 5.0 and 34.0 <= lon <= 42.0):
            wp["latitude"] = max(-5.0, min(5.0, lat))
            wp["longitude"] = max(34.0, min(42.0, lon))
    return result


def _build_prompt(state: dict[str, Any]) -> str:
    """Build user prompt from state."""
    location = state.get("location", {})
    sample = state.get("sample_data", {})

    return f"""LOCATION: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
GPS: ({location.get('lat', 'N/A')}, {location.get('lon', 'N/A')})
Terrain: {location.get('terrain', 'mixed grassland and farmland')}
Area: {location.get('area_hectares', 'unknown')} hectares

SAMPLE DATA:
  Sample ID: {sample.get('sample_id', 'unknown')}
  Initial classification: {sample.get('preliminary_result', 'pending')}
  XRF readings: {sample.get('xrf_readings', 'none available')}
  Field notes: {sample.get('notes', 'none')}

Design an optimal sampling strategy for this location."""


_DEFAULT_RESULT: dict[str, Any] = {
    "waypoints": [],
    "field_route": [],
    "grid_spacing_m": 50,
    "sampling_strategy": "grid",
    "rationale": "Default grid — agent fallback",
    "estimated_sample_count": 0,
}


async def sampling_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Sampling Agent node function.

    Generates GPS waypoints and field routes for mineral sampling.
    Includes rate limiting, retry logic, and output sanitization.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Sampling Agent starting")

    # Rate limit check
    if not rate_limiter.check("sampling"):
        logger.warning(f"[{analysis_id}] Sampling rate limited")
        return {
            "sampling_result": _DEFAULT_RESULT,
            "current_step": "analysis",
            "errors": ["Sampling Agent rate limited — using defaults"],
        }

    rate_limiter.record("sampling")

    try:
        result = await retry_with_backoff(
            llm_json_call,
            SYSTEM_PROMPT,
            _build_prompt(state),
            temperature=0.3,
            max_output_tokens=2048,
        )

        result = _validate_and_clamp(result)

        # Sanitize output
        sanitized = sanitize_output(
            result.get("rationale", ""),
            agent_role="sampling",
            user_role="field_worker",
        )

        logger.info(
            f"[{analysis_id}] Sampling complete: "
            f"{len(result.get('waypoints', []))} waypoints, "
            f"strategy={result.get('sampling_strategy', 'unknown')}"
        )

        return {
            "sampling_result": result,
            "current_step": "analysis",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Sampling complete: {len(result.get('waypoints', []))} waypoints "
                        f"using {result.get('sampling_strategy', 'unknown')} strategy."
                    ),
                }
            ],
        }

    except Exception as e:
        error_msg = f"Sampling Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "sampling_result": _DEFAULT_RESULT,
            "current_step": "analysis",
            "errors": [error_msg],
        }
