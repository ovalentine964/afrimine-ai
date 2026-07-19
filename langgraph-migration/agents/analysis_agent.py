"""
AfriMine AI — Analysis Agent
==============================

Role: Classify minerals from photos using Gemini 2.5 Flash vision,
      estimate grades from XRF data, and flag if geological context is needed.

When it runs: After Sampling Agent.
What it reads: sample_data, satellite_imagery, sampling_result.
What it writes: analysis_result.

Architecture notes:
- Gemini 2.5 Flash has native vision — send photo as base64 inline
- XRF data is parsed numerically (no LLM needed for raw readings)
- Sets requires_geology_context flag for conditional routing
- Pathfinder elements (As, Bi, Sb, Hg) trigger geology branch
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are the Analysis Agent for AfriMine AI.

Your job: Analyze a mineral sample using the provided photo and XRF data.
Classify the minerals, estimate grades, and identify pathfinder elements.

Return a JSON object with these exact keys:
{
    "minerals": [
        {
            "mineral_name": "Gold-bearing quartz",
            "confidence": 0.82,
            "grade_estimate_ppm": 5.2,
            "grade_estimate_gpt": 5.2,
            "visual_indicators": ["sulfide veining", "quartz veining", "oxidation staining"],
            "pathfinder_elements": {"As": 120.5, "Bi": 8.3, "Sb": 15.2}
        }
    ],
    "dominant_mineral": "Gold-bearing quartz",
    "overall_confidence": 0.78,
    "rock_type": "quartz vein",
    "alteration_type": "silicification",
    "xrf_data": {"Au": 5.2, "Ag": 2.1, "Cu": 45, "As": 120.5, "Fe": 3.2},
    "image_analysis_notes": "Detailed visual reasoning...",
    "requires_geology_context": true
}

Rules:
1. Confidence must be 0.0-1.0 based on visual clarity and XRF agreement
2. Grade estimates: use ppm for trace elements, gpt for gold/silver
3. Pathfinder elements: As>50ppm, Bi>5ppm, Sb>10ppm are significant for gold
4. requires_geology_context = true if: gold detected, anomalous pathfinders, or unusual rock type
5. For XRF data, convert % to ppm where needed (1% = 10,000 ppm)
6. Return ONLY valid JSON, no markdown fences"""


def _build_user_prompt(state: dict[str, Any]) -> str:
    """Build the analysis prompt from state."""
    sample = state.get("sample_data", {})
    location = state.get("location", {})

    parts = [
        f"SAMPLE: {sample.get('sample_id', 'unknown')}",
        f"LOCATION: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}",
        "",
        "XRF READINGS:",
    ]

    xrf = sample.get("xrf_readings", {})
    if isinstance(xrf, dict):
        for element, value in xrf.items():
            parts.append(f"  {element}: {value}")
    else:
        parts.append(f"  {xrf}")

    parts.extend([
        "",
        f"FIELD NOTES: {sample.get('notes', 'none')}",
        f"PRELIMINARY CLASSIFICATION: {sample.get('preliminary_result', 'pending')}",
        "",
        "Analyze this mineral sample. Identify minerals, estimate grades, and flag if geological context is needed.",
    ])

    return "\n".join(parts)


def _build_image_message(state: dict[str, Any]) -> HumanMessage | None:
    """Build a multimodal message with the sample photo if available."""
    sample = state.get("sample_data", {})
    photo_url = sample.get("photo_url")
    photo_base64 = sample.get("photo_base64")

    if photo_base64:
        # Inline base64 image for Gemini vision
        return HumanMessage(
            content=[
                {"type": "text", "text": "Analyze this rock sample photo for mineral identification."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{photo_base64}"},
                },
            ]
        )
    elif photo_url:
        return HumanMessage(
            content=[
                {"type": "text", "text": "Analyze this rock sample photo for mineral identification."},
                {"type": "image_url", "image_url": {"url": photo_url}},
            ]
        )
    return None


async def analysis_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Analysis Agent node function.

    Classifies minerals using Gemini 2.5 Flash vision and XRF data.

    Args:
        state: The current AfriMineState.

    Returns:
        Partial state update with analysis_result.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Analysis Agent starting")

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,  # Very low for consistent classification
            max_output_tokens=4096,
        )

        # Build multimodal message list
        messages = [SystemMessage(content=ANALYSIS_SYSTEM_PROMPT)]

        # Add image if available (Gemini vision)
        image_msg = _build_image_message(state)
        if image_msg:
            messages.append(image_msg)

        # Add text prompt
        messages.append(HumanMessage(content=_build_user_prompt(state)))

        response = await llm.ainvoke(messages)

        # Parse response
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

        # Enrich XRF data with pathfinder analysis
        xrf = result.get("xrf_data", {})
        pathfinders = {}
        for element in ["As", "Bi", "Sb", "Hg"]:
            if element in xrf:
                pathfinders[element] = xrf[element]

        # If Gemini didn't set pathfinder elements per-mineral, add from XRF
        for mineral in result.get("minerals", []):
            if not mineral.get("pathfinder_elements"):
                mineral["pathfinder_elements"] = pathfinders

        # Determine if geology context is needed
        requires_geology = result.get("requires_geology_context", False)
        if not requires_geology:
            # Auto-flag if gold detected or pathfinders are anomalous
            has_gold = any("gold" in m.get("mineral_name", "").lower() for m in result.get("minerals", []))
            has_anomalous_pathfinders = (
                pathfinders.get("As", 0) > 50
                or pathfinders.get("Bi", 0) > 5
                or pathfinders.get("Sb", 0) > 10
            )
            requires_geology = has_gold or has_anomalous_pathfinders
            result["requires_geology_context"] = requires_geology

        logger.info(
            f"[{analysis_id}] Analysis Agent complete: "
            f"{len(result.get('minerals', []))} minerals, "
            f"dominant={result.get('dominant_mineral', 'unknown')}, "
            f"requires_geology={requires_geology}"
        )

        return {
            "analysis_result": result,
            "current_step": "router",
            "messages": [
                HumanMessage(
                    content=f"Analysis complete: {result.get('dominant_mineral', 'unknown')} "
                            f"(confidence {result.get('overall_confidence', 0):.0%}). "
                            f"Geology context needed: {requires_geology}",
                    name="analysis_agent",
                )
            ],
        }

    except json.JSONDecodeError as e:
        error_msg = f"Analysis Agent failed to parse LLM response: {e}"
        logger.error(f"[{analysis_id}] {error_msg}")
        return {
            "analysis_result": {
                "minerals": [],
                "dominant_mineral": "unknown",
                "overall_confidence": 0.0,
                "requires_geology_context": True,  # Default to geology on failure
            },
            "current_step": "router",
            "errors": [error_msg],
        }

    except Exception as e:
        error_msg = f"Analysis Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "analysis_result": {},
            "current_step": "router",
            "errors": [error_msg],
        }
