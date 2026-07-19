"""
AfriMine AI — Compliance Agent
================================

Role: Check Kenya Mining Act 2016 compliance, license requirements,
      EIA status, royalty calculations, and community agreement obligations.

When it runs: Last node before END (after Report Agent).
What it reads: report_result, market_result, location, analysis_result.
What it writes: compliance_result.

Architecture notes:
- This is the final gate — no output reaches the user without compliance check
- Implements human-in-the-loop: if is_compliant=False, graph pauses for manual review
- Kenya Mining Act 2016 key provisions are embedded in the prompt
- Royalty calculation uses the market agent's deposit value
- Future: integrate with eCitizen API for real-time license verification
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

KENYA_MINING_ACT_KNOWLEDGE = """
=== KENYA MINING ACT 2016 — KEY PROVISIONS ===

LICENSE TYPES (in order of progression):
1. Reconnaissance Permit (RP)
   - Duration: 1 year (renewable)
   - Area: Up to 1,000 km²
   - Activity: Non-invasive surface surveys only
   - Fee: KES 10,000 (~$77)

2. Prospecting License (PL)
   - Duration: 3 years (renewable twice, 2 years each)
   - Area: Up to 50 km² (individual), 200 km² (company)
   - Activity: Drilling, trenching, sampling
   - Fee: KES 50,000 (~$385)
   - Requirements: RP or mineral rights holder consent

3. Mining License (ML)
   - Duration: 25 years (renewable)
   - Activity: Full extraction
   - Fee: KES 500,000 (~$3,850)
   - Requirements: EIA approved, Mine Plan, Financial assurance

4. Artisanal Mining Permit (AMP)
   - Duration: 2 years (renewable)
   - Area: Up to 1 hectare
   - Activity: Manual extraction only
   - Fee: KES 2,000 (~$15)
   - Requirements: Kenyan citizen, cooperative membership

ENVIRONMENTAL IMPACT ASSESSMENT (EIA):
- Required for ALL mining licenses (PL and above)
- Conducted by NEMA-licensed firm
- Duration: 3-12 months
- Cost: KES 500,000 - 5,000,000 (~$3,850 - $38,500)
- Community consultation mandatory

ROYALTY RATES:
- Base minerals (gold, copper, etc.): 5% of gross revenue
- Gemstones: 10%
- Industrial minerals: 2%
- Petroleum: Production-sharing contract

COMMUNITY AGREEMENTS:
- Mining Act Section 178: Community Development Agreement (CDA)
- Required for ML and large-scale PL
- Minimum 1% of annual gross revenue to community
- Must include: employment, local procurement, social projects

KEY REGULATORY BODIES:
- Ministry of Mining, Blue Economy and Maritime Affairs
- Directorate of Geological Survey (DGS)
- National Environment Management Authority (NEMA)
- County Government (Migori County for this project)

PROHIBITED AREAS:
- National parks and reserves
- Water catchment areas (within 30m of rivers)
- Urban areas (without special permit)
- Gazetted archaeological/historical sites

ARTISANAL MINING SPECIAL PROVISIONS:
- Section 91-97: Artisanal mining committees
- Must be registered with county government
- Mercury use prohibited (since 2019 amendments)
- Equipment limitations (no mechanized processing)
"""

COMPLIANCE_SYSTEM_PROMPT = f"""You are the Compliance Agent for AfriMine AI.

Your job: Check the analysis and report against Kenya Mining Act 2016 requirements.
Identify any compliance issues and provide actionable recommendations.

{KENYA_MINING_ACT_KNOWLEDGE}

Return a JSON object with these exact keys:
{{
    "license_type_required": "Prospecting License",
    "license_status": "not_held",
    "eia_required": true,
    "eia_status": "not_submitted",
    "royalty_percentage": 5.0,
    "community_agreement_required": true,
    "compliance_issues": [
        "No Prospecting License held for this area",
        "EIA not yet submitted to NEMA"
    ],
    "regulatory_recommendations": [
        "Apply for Prospecting License at DGS office in Kisumu",
        "Engage NEMA-licensed EIA firm before drilling activities",
        "Initiate Community Development Agreement with local leaders"
    ],
    "is_compliant": false
}}

Rules:
1. is_compliant = true ONLY if ALL required licenses, EIAs, and agreements are in place
2. For initial analysis (no prior licenses), is_compliant will almost always be false
3. compliance_issues must reference specific sections of the Mining Act
4. regulatory_recommendations must be actionable with specific offices/agencies
5. royalty_percentage is always 5% for gold/copper (base minerals)
6. community_agreement_required = true for any extraction activity
7. Consider artisanal permits for small areas (<1 hectare, manual methods)
8. Return ONLY valid JSON, no markdown fences"""


async def compliance_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Compliance Agent node function.

    Checks Kenya Mining Act 2016 compliance and regulatory requirements.

    Args:
        state: The current AfriMineState.

    Returns:
        Partial state update with compliance_result.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Compliance Agent starting")

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,  # Very low for regulatory accuracy
            max_output_tokens=4096,
        )

        market = state.get("market_result", {})
        report = state.get("report_result", {})
        location = state.get("location", {})
        analysis = state.get("analysis_result", {})

        user_prompt = f"""COMPLIANCE CHECK REQUEST

=== PROJECT DETAILS ===
Location: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
Area: {location.get('area_hectares', 'unknown')} hectares
Activity: Mineral prospecting and sampling

=== ANALYSIS SUMMARY ===
Dominant mineral: {analysis.get('dominant_mineral', 'unknown')}
Deposit model: {state.get('geology_result', {}).get('deposit_model', 'unknown')}
Deposit value: ${market.get('deposit_value_estimate_usd', 0):,.2f}

=== RECOMMENDATION ===
{report.get('recommendation', 'No recommendation yet')}

=== EXISTING LICENSES ===
{json.dumps(state.get('sample_data', {}).get('licenses', {}), indent=2)}

Check compliance against Kenya Mining Act 2016."""

        response = await llm.ainvoke([
            SystemMessage(content=COMPLIANCE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

        # Ensure royalty matches market data
        result["royalty_percentage"] = market.get("royalty_rate_pct", 5.0)

        logger.info(
            f"[{analysis_id}] Compliance Agent complete: "
            f"compliant={result.get('is_compliant')}, "
            f"license={result.get('license_type_required')}, "
            f"issues={len(result.get('compliance_issues', []))}"
        )

        return {
            "compliance_result": result,
            "current_step": "completed",
            "messages": [
                HumanMessage(
                    content=f"Compliance: {'PASS' if result.get('is_compliant') else 'BLOCKED'}. "
                            f"License needed: {result.get('license_type_required', 'unknown')}. "
                            f"{len(result.get('compliance_issues', []))} issues found.",
                    name="compliance_agent",
                )
            ],
        }

    except json.JSONDecodeError as e:
        error_msg = f"Compliance Agent failed to parse LLM response: {e}"
        logger.error(f"[{analysis_id}] {error_msg}")
        return {
            "compliance_result": {
                "is_compliant": False,
                "compliance_issues": [f"Compliance check failed: {error_msg}"],
                "regulatory_recommendations": ["Manual compliance review required"],
            },
            "current_step": "completed",
            "errors": [error_msg],
        }

    except Exception as e:
        error_msg = f"Compliance Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "compliance_result": {},
            "current_step": "completed",
            "errors": [error_msg],
        }
