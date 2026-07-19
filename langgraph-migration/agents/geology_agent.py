"""
AfriMine AI — Geology Agent
=============================

Role: Interpret geological context — belt identification, deposit models,
      pathfinder element correlation, and structural setting analysis.

When it runs: In parallel with Market Agent, after Analysis Agent (conditional).
What it reads: analysis_result, location, sample_data.
What it writes: geology_result.

Architecture notes:
- This is the most knowledge-intensive agent
- Uses NVIDIA NIM (MiniMax M3) with RAG-style prompting and Migori Belt geological knowledge
- Pathfinder interpretation (As → Au correlation) is domain-critical
- Runs in a PARALLEL branch with Market Agent (LangGraph fan-out)
- Both branches must complete before Report Agent (fan-in)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Geological knowledge base for Migori Belt — embedded in prompt as context.
# In production, this would be a Supabase pgvector RAG store.
MIGORI_BELT_KNOWLEDGE = """
=== MIGORI GREENSTONE BELT — GEOLOGICAL KNOWLEDGE BASE ===

Location: Migori County, Western Kenya (lat: -1.5 to -0.8, lon: 34.2 to 35.0)
Age: Archean to Paleoproterozoic (2.5–2.0 Ga)
Host rocks: Nyanzian System volcanics + sediments

DEPOSIT MODELS:
1. Orogenic Gold (primary model for Migori)
   - Host: Quartz veins in shear zones
   - Pathfinder elements: As (arsenic) > 50 ppm, Bi (bismuth) > 5 ppm
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
- Ferrous iron index (B4/B3) → Sulfide weathering

STRUCTURAL FEATURES:
- Major shear zone: Macalder–Nyatike trend (NNW-SSE)
- Secondary structures: NE-SW cross-cutting faults
- Fold interference zones: Favorable for gold precipitation

KNOWN ANOMALIES IN MIGORI:
- Macalder copper-gold mine (historical production: 1.5 Mt @ 1.2% Cu, 2 g/t Au)
- Nyatike artisanal goldfield (alluvial + primary)
- Masara gold occurrences (quartz vein hosted)
- Transmara copper anomalies

JORC RESOURCE CLASSIFICATION RULES:
- Measured: <500m drill spacing, high confidence
- Indicated: 500–1000m spacing, reasonable confidence
- Inferred: >1000m spacing or limited sampling, low confidence
- For artisanal sites with no drilling → Inferred category maximum
"""

GEOLOGY_SYSTEM_PROMPT = f"""You are the Geology Agent for AfriMine AI.

Your job: Interpret the geological context of a mineral sample from the Migori
Greenstone Belt in Kenya. Use the knowledge base below to identify the deposit
model, structural setting, and resource potential.

{MIGORI_BELT_KNOWLEDGE}

Return a JSON object with these exact keys:
{{
    "belt_name": "Migori Greenstone Belt",
    "formation": "Nyanzian System",
    "structural_setting": "NNW-trending shear zone, fold hinge",
    "deposit_model": "orogenic gold",
    "pathfinder_interpretation": "As at 120 ppm strongly indicates gold association...",
    "alteration_mapping": {{
        "silicification": "B11/B12 ratio suggests silica enrichment",
        "oxidation": "B4/B2 ratio indicates gossan development"
    }},
    "resource_potential": "high",
    "comparable_deposits": ["Macalder mine", "Nyatike goldfields"],
    "recommendations": "Proceed with detailed sampling along the NNW shear zone..."
}}

Rules:
1. Base interpretations on the provided knowledge base — don't fabricate geology
2. Pathfinder interpretation must explain As→Au, Bi→Au, or Cu-Zn→VMS correlations
3. resource_potential: "high" if gold + anomalous pathfinders, "medium" if pathfinders only, "low" otherwise
4. Always recommend next steps (drilling, trenching, geophysics)
5. comparable_deposits must be real deposits from the knowledge base
6. Return ONLY valid JSON, no markdown fences"""


async def geology_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Geology Agent node function.

    Interprets geological context using domain knowledge and analysis results.

    Args:
        state: The current AfriMineState.

    Returns:
        Partial state update with geology_result.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Geology Agent starting (parallel branch)")

    try:
        # NVIDIA NIM via OpenAI-compatible API (fallback: Groq → Mistral → Ollama)
        from llm_provider import get_llm_with_fallback
        llm, _provider = get_llm_with_fallback(
            temperature=0.3,
            max_tokens=4096,
        )

        analysis = state.get("analysis_result", {})
        location = state.get("location", {})

        user_prompt = f"""GEOLOGICAL ANALYSIS REQUEST

Location: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
GPS: ({location.get('lat', 'N/A')}, {location.get('lon', 'N/A')})

ANALYSIS RESULTS:
- Dominant mineral: {analysis.get('dominant_mineral', 'unknown')}
- Rock type: {analysis.get('rock_type', 'unknown')}
- Alteration type: {analysis.get('alteration_type', 'unknown')}
- Overall confidence: {analysis.get('overall_confidence', 0):.0%}

MINERAL DETAILS:
{json.dumps(analysis.get('minerals', []), indent=2)}

XRF DATA:
{json.dumps(analysis.get('xrf_data', {}), indent=2)}

PATHFINDER ELEMENTS:
{json.dumps(
    {k: v for m in analysis.get('minerals', []) for k, v in m.get('pathfinder_elements', {}).items()},
    indent=2
)}

Interpret the geological context and determine the deposit model."""

        response = await llm.ainvoke([
            SystemMessage(content=GEOLOGY_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

        logger.info(
            f"[{analysis_id}] Geology Agent complete: "
            f"model={result.get('deposit_model', 'unknown')}, "
            f"potential={result.get('resource_potential', 'unknown')}"
        )

        return {
            "geology_result": result,
            "current_step": "report_fan_in",
            "messages": [
                HumanMessage(
                    content=f"Geology: {result.get('deposit_model', 'unknown')} deposit model, "
                            f"resource potential: {result.get('resource_potential', 'unknown')}.",
                    name="geology_agent",
                )
            ],
        }

    except json.JSONDecodeError as e:
        error_msg = f"Geology Agent failed to parse LLM response: {e}"
        logger.error(f"[{analysis_id}] {error_msg}")
        return {
            "geology_result": {
                "belt_name": "Migori Greenstone Belt",
                "deposit_model": "unknown",
                "resource_potential": "insufficient_data",
                "pathfinder_interpretation": "Parsing error — manual review required",
            },
            "current_step": "report_fan_in",
            "errors": [error_msg],
        }

    except Exception as e:
        error_msg = f"Geology Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "geology_result": {},
            "current_step": "report_fan_in",
            "errors": [error_msg],
        }
