"""
AfriMine AI — Geology Agent (Production)
==========================================

Interprets geological context — belt identification, deposit models,
pathfinder element correlation, and structural setting analysis.
Uses RAG-style prompting with Migori Belt geological knowledge.

Node position: Analysis → GEOLOGY (parallel with Market) → merge_branches
LLM: Gemini 2.5 Flash
Tools: geology-mcp, satellite-mcp, geostats-mcp
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base import llm_json_call, retry_with_backoff
from security.middleware import rate_limiter, sanitize_output

logger = logging.getLogger("afrimine.geology")

# Geological knowledge base for Migori Belt — embedded in prompt as context.
MIGORI_BELT_KNOWLEDGE = """
=== MIGORI GREENSTONE BELT — GEOLOGICAL KNOWLEDGE BASE ===

Location: Migori County, Western Kenya (lat: -1.5 to -0.8, lon: 34.2 to 35.0)
Age: Archean to Paleoproterozoic (2.5–2.0 Ga)
Host rocks: Nyanzian System volcanics + sediments

DEPOSIT MODELS:
1. Orogenic Gold (primary model for Migori)
   - Host: Quartz veins in shear zones
   - Pathfinder elements: As > 50 ppm, Bi > 5 ppm
   - Alteration: Silicification, sericitization, carbonatization
   - Structural control: NNW-trending shear zones, fold hinges
   - Grade: 1–20 g/t Au (high-grade shoots: 30+ g/t)
   - Examples: Macalder mine, Nyatike goldfields

2. Volcanogenic Massive Sulfide (VMS) — secondary
   - Host: Mafic volcanic rocks at stratigraphic contact
   - Pathfinder: Cu > 1000 ppm, Zn > 500 ppm, Ba > 2000 ppm
   - Alteration: Chlorite, sericite, silica
   - Grade: 0.5–3% Cu, 1–5% Zn

3. Laterite Gold (supergene enrichment)
   - Host: Laterite profiles over primary mineralization
   - Depth: 0–30m below surface
   - Grade: 0.5–5 g/t Au
   - Recovery: Simple gravity separation (60–70%)

ALTERATION BAND RATIOS (Sentinel-2):
- B4/B2 > 1.5 → Iron oxidation (gossan indicator)
- B11/B12 > 1.2 → Silicification
- B8A/B4 > 1.1 → Clay alteration (sericite/kaolinite)

STRUCTURAL FEATURES:
- Major shear zone: Macalder–Nyatike trend (NNW-SSE)
- Secondary structures: NE-SW cross-cutting faults
- Fold interference zones: Favorable for gold precipitation

KNOWN ANOMALIES:
- Macalder copper-gold mine (1.5 Mt @ 1.2% Cu, 2 g/t Au)
- Nyatike artisanal goldfield (alluvial + primary)
- Masara gold occurrences (quartz vein hosted)
- Transmara copper anomalies

JORC CLASSIFICATION:
- Measured: <500m drill spacing
- Indicated: 500–1000m spacing
- Inferred: >1000m or limited sampling
- Artisanal sites → Inferred maximum
"""

SYSTEM_PROMPT = f"""You are the Geology Agent for AfriMine AI.

Interpret the geological context of a mineral sample from the Migori
Greenstone Belt in Kenya.

{MIGORI_BELT_KNOWLEDGE}

Return a JSON object with these exact keys:
{{
    "belt_name": "Migori Greenstone Belt",
    "formation": "Nyanzian System",
    "structural_setting": "NNW-trending shear zone",
    "deposit_model": "orogenic gold",
    "pathfinder_interpretation": "As at 120 ppm strongly indicates gold...",
    "alteration_mapping": {{
        "silicification": "B11/B12 ratio suggests silica enrichment"
    }},
    "resource_potential": "high",
    "comparable_deposits": ["Macalder mine", "Nyatike goldfields"],
    "recommendations": "Proceed with detailed sampling along NNW shear zone..."
}}

Rules:
1. Base interpretations on the knowledge base — don't fabricate geology
2. Pathfinder interpretation must explain As→Au, Bi→Au, or Cu-Zn→VMS correlations
3. resource_potential: "high" if gold + anomalous pathfinders, "medium" if pathfinders only
4. Always recommend next steps
5. comparable_deposits must be real deposits from the knowledge base
6. Return ONLY valid JSON, no markdown fences"""


def _build_prompt(state: dict[str, Any]) -> str:
    analysis = state.get("analysis_result", {})
    location = state.get("location", {})

    minerals_json = json.dumps(analysis.get("minerals", []), indent=2)
    xrf_json = json.dumps(analysis.get("xrf_data", {}), indent=2)

    pathfinders = {}
    for m in analysis.get("minerals", []):
        pathfinders.update(m.get("pathfinder_elements", {}))
    pf_json = json.dumps(pathfinders, indent=2)

    return f"""GEOLOGICAL ANALYSIS REQUEST

Location: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
GPS: ({location.get('lat', 'N/A')}, {location.get('lon', 'N/A')})

ANALYSIS RESULTS:
- Dominant mineral: {analysis.get('dominant_mineral', 'unknown')}
- Rock type: {analysis.get('rock_type', 'unknown')}
- Alteration type: {analysis.get('alteration_type', 'unknown')}
- Confidence: {analysis.get('overall_confidence', 0):.0%}

MINERAL DETAILS:
{minerals_json}

XRF DATA:
{xrf_json}

PATHFINDER ELEMENTS:
{pf_json}

Interpret the geological context and determine the deposit model."""


async def geology_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Geology Agent node function.

    Interprets geological context using domain knowledge and analysis results.
    Runs in PARALLEL with Market Agent.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Geology Agent starting (parallel branch)")

    if not rate_limiter.check("geology"):
        return {
            "geology_result": {
                "belt_name": "Migori Greenstone Belt",
                "deposit_model": "unknown",
                "resource_potential": "insufficient_data",
            },
            "current_step": "merge",
            "errors": ["Geology Agent rate limited"],
        }

    rate_limiter.record("geology")

    try:
        result = await retry_with_backoff(
            llm_json_call,
            SYSTEM_PROMPT,
            _build_prompt(state),
            temperature=0.3,
            max_output_tokens=4096,
        )

        # Sanitize recommendations
        if result.get("recommendations"):
            sanitized = sanitize_output(result["recommendations"], "geology")
            result["recommendations"] = sanitized.output

        logger.info(
            f"[{analysis_id}] Geology complete: "
            f"model={result.get('deposit_model', 'unknown')}, "
            f"potential={result.get('resource_potential', 'unknown')}"
        )

        return {
            "geology_result": result,
            "current_step": "merge",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Geology: {result.get('deposit_model', 'unknown')} deposit model, "
                        f"resource potential: {result.get('resource_potential', 'unknown')}."
                    ),
                }
            ],
        }

    except Exception as e:
        error_msg = f"Geology Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "geology_result": {
                "belt_name": "Migori Greenstone Belt",
                "deposit_model": "unknown",
                "resource_potential": "insufficient_data",
                "pathfinder_interpretation": "Error — manual review required",
            },
            "current_step": "merge",
            "errors": [error_msg],
        }
