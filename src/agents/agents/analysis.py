"""
AfriMine AI — Analysis Agent (Production)
===========================================

Classifies minerals from photos using Gemini 2.5 Flash vision,
estimates grades from XRF data, and flags if geological context is needed.

Node position: Sampling → ANALYSIS → Router (fan-out to Geology/Market)
LLM: Gemini 2.5 Flash with vision
Tools: mineral-classifier-mcp, image-processor-mcp
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agents.base import create_llm, parse_json_response, retry_with_backoff, SECURITY_PREAMBLE
from security.middleware import rate_limiter, sanitize_output

logger = logging.getLogger("afrimine.analysis")

SYSTEM_PROMPT = """You are the Analysis Agent for AfriMine AI.

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
            "visual_indicators": ["sulfide veining", "quartz veining"],
            "pathfinder_elements": {"As": 120.5, "Bi": 8.3}
        }
    ],
    "dominant_mineral": "Gold-bearing quartz",
    "overall_confidence": 0.78,
    "rock_type": "quartz vein",
    "alteration_type": "silicification",
    "xrf_data": {"Au": 5.2, "Ag": 2.1, "Cu": 45, "As": 120.5},
    "image_analysis_notes": "Detailed visual reasoning...",
    "requires_geology_context": true
}

Rules:
1. Confidence 0.0-1.0 based on visual clarity and XRF agreement
2. Grade: ppm for trace elements, gpt for gold/silver
3. Pathfinder elements: As>50ppm, Bi>5ppm, Sb>10ppm significant for gold
4. requires_geology_context = true if gold detected or anomalous pathfinders
5. Convert % to ppm where needed (1% = 10,000 ppm)
6. Return ONLY valid JSON, no markdown fences"""


def _build_prompt(state: dict[str, Any]) -> str:
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
        "Analyze this mineral sample. Identify minerals, estimate grades, "
        "and flag if geological context is needed.",
    ])

    return "\n".join(parts)


def _build_image_message(state: dict[str, Any]) -> HumanMessage | None:
    """Build multimodal message with sample photo if available."""
    sample = state.get("sample_data", {})
    photo_base64 = sample.get("photo_base64")
    photo_url = sample.get("photo_url")

    if photo_base64:
        return HumanMessage(
            content=[
                {"type": "text", "text": "Analyze this rock sample photo for mineral identification."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{photo_base64}"}},
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
    Sets requires_geology_context flag for conditional routing.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Analysis Agent starting")

    if not rate_limiter.check("analysis"):
        return {
            "analysis_result": {
                "minerals": [],
                "dominant_mineral": "unknown",
                "overall_confidence": 0.0,
                "requires_geology_context": True,
            },
            "current_step": "router",
            "errors": ["Analysis Agent rate limited"],
        }

    rate_limiter.record("analysis")

    try:
        llm = create_llm(temperature=0.2, max_output_tokens=4096)

        messages = [SystemMessage(content=SECURITY_PREAMBLE + "\n" + SYSTEM_PROMPT)]

        image_msg = _build_image_message(state)
        if image_msg:
            messages.append(image_msg)

        messages.append(HumanMessage(content=_build_prompt(state)))

        async def _call():
            response = await llm.ainvoke(messages)
            return parse_json_response(response.content)

        result = await retry_with_backoff(_call)

        # Enrich pathfinder elements from XRF
        xrf = result.get("xrf_data", {})
        pathfinders = {k: xrf[k] for k in ("As", "Bi", "Sb", "Hg") if k in xrf}

        for mineral in result.get("minerals", []):
            if not mineral.get("pathfinder_elements"):
                mineral["pathfinder_elements"] = pathfinders

        # Auto-flag geology requirement
        requires_geology = result.get("requires_geology_context", False)
        if not requires_geology:
            has_gold = any(
                "gold" in m.get("mineral_name", "").lower()
                for m in result.get("minerals", [])
            )
            has_anomalous = (
                pathfinders.get("As", 0) > 50
                or pathfinders.get("Bi", 0) > 5
                or pathfinders.get("Sb", 0) > 10
            )
            requires_geology = has_gold or has_anomalous
            result["requires_geology_context"] = requires_geology

        # Sanitize output notes
        if result.get("image_analysis_notes"):
            sanitized = sanitize_output(result["image_analysis_notes"], "analysis")
            result["image_analysis_notes"] = sanitized.output

        logger.info(
            f"[{analysis_id}] Analysis complete: "
            f"{len(result.get('minerals', []))} minerals, "
            f"dominant={result.get('dominant_mineral', 'unknown')}, "
            f"requires_geology={requires_geology}"
        )

        return {
            "analysis_result": result,
            "current_step": "router",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Analysis complete: {result.get('dominant_mineral', 'unknown')} "
                        f"(confidence {result.get('overall_confidence', 0):.0%}). "
                        f"Geology context needed: {requires_geology}"
                    ),
                }
            ],
        }

    except Exception as e:
        error_msg = f"Analysis Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "analysis_result": {
                "minerals": [],
                "dominant_mineral": "unknown",
                "overall_confidence": 0.0,
                "requires_geology_context": True,
            },
            "current_step": "router",
            "errors": [error_msg],
        }
