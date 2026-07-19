"""
AfriMine AI — Sampling Agent
=============================

Role: Plan field sampling strategies, generate GPS waypoints,
      and optimize walking routes for field workers in Nyatike.

When it runs: First node after START.
What it reads: location, sample_data, satellite_imagery.
What it writes: sampling_result.

Architecture notes:
- Uses Gemini 2.5 Flash for spatial reasoning (grid layout, terrain analysis)
- No external tool calls — pure LLM reasoning over input data
- Output is validated against GPS coordinate bounds (Kenya: -5°S to 5°N, 34°E to 42°E)
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

SAMPLING_SYSTEM_PROMPT = """You are the Sampling Agent for AfriMine AI, a mineral detection
platform serving mining communities in Migori County, Kenya.

Your job: Given a location and sample data, design an optimal sampling strategy.

You must return a JSON object with these exact keys:
{
    "waypoints": [
        {"latitude": -1.234, "longitude": 34.567, "elevation_m": 1450, "rationale": "..."},
        ...
    ],
    "field_route": [
        {"latitude": -1.234, "longitude": 34.567, "order": 1},
        ...
    ],
    "grid_spacing_m": 50,
    "sampling_strategy": "grid",
    "rationale": "Detailed explanation of why this layout...",
    "estimated_sample_count": 12
}

Rules:
1. All GPS coordinates MUST be within Migori County bounds (lat: -1.5 to -0.8, lon: 34.2 to 35.0)
2. Grid spacing depends on terrain: 25m for steep terrain, 50m for flat, 100m for large areas
3. Prioritize areas near known geological features (rivers, fault lines, color anomalies)
4. Field route should minimize walking distance (nearest-neighbor heuristic)
5. Estimate sample count based on area and grid spacing
6. Always include 3-8 waypoints for a standard prospecting license area
7. Return ONLY valid JSON, no markdown fences"""


def _validate_waypoints(result: dict[str, Any]) -> bool:
    """Validate that all waypoints are within Kenya bounds."""
    for wp in result.get("waypoints", []):
        lat = wp.get("latitude", 0)
        lon = wp.get("longitude", 0)
        if not (-5.0 <= lat <= 5.0 and 34.0 <= lon <= 42.0):
            logger.warning(f"Waypoint outside Kenya bounds: ({lat}, {lon})")
            return False
    return True


def _build_user_prompt(state: dict[str, Any]) -> str:
    """Construct the user prompt from state data."""
    location = state.get("location", {})
    sample_data = state.get("sample_data", {})

    parts = [
        f"LOCATION: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya",
        f"GPS: ({location.get('lat', 'N/A')}, {location.get('lon', 'N/A')})",
        f"Terrain: {location.get('terrain', 'mixed grassland and farmland')}",
        f"Area size: {location.get('area_hectares', 'unknown')} hectares",
        "",
        f"SAMPLE DATA:",
        f"  Sample ID: {sample_data.get('sample_id', 'unknown')}",
        f"  Initial classification: {sample_data.get('preliminary_result', 'pending')}",
        f"  XRF readings: {sample_data.get('xrf_readings', 'none available')}",
        f"  Field notes: {sample_data.get('notes', 'none')}",
        "",
        "Design an optimal sampling strategy for this location.",
    ]
    return "\n".join(parts)


async def sampling_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Sampling Agent node function.

    Generates GPS waypoints and field routes for mineral sampling.

    Args:
        state: The current AfriMineState.

    Returns:
        Partial state update with sampling_result and next step.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Sampling Agent starting")

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,  # Low temp for consistent spatial reasoning
            max_output_tokens=2048,
        )

        user_prompt = _build_user_prompt(state)

        response = await llm.ainvoke([
            SystemMessage(content=SAMPLING_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        # Parse JSON from response
        import json
        raw = response.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

        # Validate GPS bounds
        if not _validate_waypoints(result):
            logger.warning(f"[{analysis_id}] Waypoint validation failed, clamping coordinates")
            # Clamp to Kenya bounds as safety net
            for wp in result.get("waypoints", []):
                wp["latitude"] = max(-5.0, min(5.0, wp.get("latitude", 0)))
                wp["longitude"] = max(34.0, min(42.0, wp.get("longitude", 0)))

        logger.info(
            f"[{analysis_id}] Sampling Agent complete: "
            f"{len(result.get('waypoints', []))} waypoints, "
            f"strategy={result.get('sampling_strategy', 'unknown')}"
        )

        return {
            "sampling_result": result,
            "current_step": "analysis",
            "messages": [
                HumanMessage(
                    content=f"Sampling complete: {len(result.get('waypoints', []))} waypoints "
                            f"using {result.get('sampling_strategy', 'unknown')} strategy.",
                    name="sampling_agent",
                )
            ],
        }

    except json.JSONDecodeError as e:
        error_msg = f"Sampling Agent failed to parse LLM response: {e}"
        logger.error(f"[{analysis_id}] {error_msg}")
        return {
            "sampling_result": {
                "waypoints": [],
                "field_route": [],
                "grid_spacing_m": 50,
                "sampling_strategy": "grid",
                "rationale": "Default grid — LLM parsing failed",
                "estimated_sample_count": 0,
            },
            "current_step": "analysis",
            "errors": [error_msg],
        }

    except Exception as e:
        error_msg = f"Sampling Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "sampling_result": {},
            "current_step": "analysis",
            "errors": [error_msg],
        }
