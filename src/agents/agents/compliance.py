"""
AfriMine AI — Compliance Agent (Production)
=============================================

Checks Kenya Mining Act 2016 compliance, license requirements,
EIA status, royalty calculations, and community agreement obligations.

Node position: Report → COMPLIANCE → END
LLM: Gemini 2.5 Flash
Tools: compliance-mcp, regulatory-mcp
Supports human-in-the-loop for blocking issues.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base import llm_json_call, retry_with_backoff
from config import settings
from security.middleware import rate_limiter

logger = logging.getLogger("afrimine.compliance")

KENYA_MINING_ACT = """
=== KENYA MINING ACT 2016 — KEY PROVISIONS ===

LICENSE TYPES:
1. Reconnaissance Permit (RP) — 1yr, up to 1000 km², surface surveys only, KES 10,000
2. Prospecting License (PL) — 3yr (renewable 2x), up to 50 km², KES 50,000
3. Mining License (ML) — 25yr, full extraction, KES 500,000
4. Artisanal Mining Permit (AMP) — 2yr, up to 1 hectare, manual only, KES 2,000

EIA: Required for PL and above. NEMA-licensed firm. 3-12 months. KES 500K-5M.
ROYALTY: Base minerals 5%, gemstones 10%, industrial 2%.
COMMUNITY: Section 178 CDA required for ML/large PL. Min 1% gross revenue.
PROHIBITED: National parks, water catchment (30m rivers), urban areas, archaeological sites.
ARTISANAL: Sections 91-97, registered with county, mercury prohibited since 2019.
BODIES: Ministry of Mining, DGS, NEMA, County Government.
"""

SYSTEM_PROMPT = f"""You are the Compliance Agent for AfriMine AI.

Check the analysis against Kenya Mining Act 2016 requirements.

{KENYA_MINING_ACT}

Return a JSON object with these exact keys:
{{
    "license_type_required": "Prospecting License",
    "license_status": "not_held",
    "eia_required": true,
    "eia_status": "not_submitted",
    "royalty_percentage": 5.0,
    "community_agreement_required": true,
    "compliance_issues": ["No PL held", "EIA not submitted"],
    "regulatory_recommendations": ["Apply for PL at DGS Kisumu", "Engage NEMA EIA firm"],
    "is_compliant": false
}}

Rules:
1. is_compliant = true ONLY if ALL licenses, EIAs, agreements are in place
2. For initial analysis (no prior licenses), is_compliant almost always false
3. compliance_issues must reference specific Mining Act sections
4. recommendations must be actionable with specific offices/agencies
5. royalty_percentage: 5% for gold/copper
6. community_agreement_required = true for extraction
7. Consider artisanal permits for <1 hectare, manual methods
8. Return ONLY valid JSON, no markdown fences"""


def _build_prompt(state: dict[str, Any]) -> str:
    market = state.get("market_result", {})
    report = state.get("report_result", {})
    location = state.get("location", {})
    analysis = state.get("analysis_result", {})
    geology = state.get("geology_result", {})

    return f"""COMPLIANCE CHECK REQUEST

=== PROJECT DETAILS ===
Location: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
Area: {location.get('area_hectares', 'unknown')} hectares
Activity: Mineral prospecting and sampling

=== ANALYSIS SUMMARY ===
Dominant mineral: {analysis.get('dominant_mineral', 'unknown')}
Deposit model: {geology.get('deposit_model', 'unknown')}
Deposit value: ${market.get('deposit_value_estimate_usd', 0):,.2f}

=== RECOMMENDATION ===
{report.get('recommendation', 'No recommendation yet')}

=== EXISTING LICENSES ===
{json.dumps(state.get('sample_data', {}).get('licenses', {}), indent=2)}

Check compliance against Kenya Mining Act 2016."""


async def compliance_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Compliance Agent node function.

    Checks Kenya Mining Act 2016 compliance and regulatory requirements.
    Final gate before pipeline completion.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Compliance Agent starting")

    if not rate_limiter.check("compliance"):
        return {
            "compliance_result": {
                "is_compliant": False,
                "compliance_issues": ["Compliance check rate limited"],
                "regulatory_recommendations": ["Manual compliance review required"],
            },
            "current_step": "completed",
            "errors": ["Compliance Agent rate limited"],
        }

    rate_limiter.record("compliance")

    try:
        result = await retry_with_backoff(
            llm_json_call,
            SYSTEM_PROMPT,
            _build_prompt(state),
            temperature=0.2,
            max_output_tokens=4096,
        )

        # Ensure royalty matches market data
        market = state.get("market_result", {})
        result["royalty_percentage"] = market.get("royalty_rate_pct", 5.0)

        is_compliant = result.get("is_compliant", False)
        issues_count = len(result.get("compliance_issues", []))

        logger.info(
            f"[{analysis_id}] Compliance complete: "
            f"compliant={is_compliant}, "
            f"license={result.get('license_type_required', 'unknown')}, "
            f"issues={issues_count}"
        )

        # Log compliance issues as warnings
        for issue in result.get("compliance_issues", []):
            logger.warning(f"[{analysis_id}] Compliance issue: {issue}")

        return {
            "compliance_result": result,
            "current_step": "completed",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Compliance: {'PASS' if is_compliant else 'BLOCKED'}. "
                        f"License needed: {result.get('license_type_required', 'unknown')}. "
                        f"{issues_count} issues found."
                    ),
                }
            ],
        }

    except Exception as e:
        error_msg = f"Compliance Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "compliance_result": {
                "is_compliant": False,
                "compliance_issues": [f"Compliance check failed: {error_msg}"],
                "regulatory_recommendations": ["Manual compliance review required"],
            },
            "current_step": "completed",
            "errors": [error_msg],
        }
