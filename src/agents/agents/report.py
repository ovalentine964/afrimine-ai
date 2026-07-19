"""
AfriMine AI — Report Agent (Production)
=========================================

Generates investor-ready reports by synthesizing all agent outputs
into structured HTML suitable for PDF conversion.

Node position: merge_branches → REPORT → Compliance (or loop back)
LLM: Gemini 2.5 Flash
Tools: report-mcp, storage-mcp
Supports iterative refinement (max 3 loops).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from agents.base import llm_json_call, retry_with_backoff
from config import settings
from security.middleware import rate_limiter, sanitize_output

logger = logging.getLogger("afrimine.report")

SYSTEM_PROMPT = """You are the Report Agent for AfriMine AI.

Synthesize all analysis results into an investor-ready technical report.

Return a JSON object with these exact keys:
{
    "executive_summary": "2-3 paragraph overview...",
    "key_findings": ["Finding 1", "Finding 2"],
    "risk_summary": ["Risk 1", "Risk 2"],
    "recommendation": "Proceed to Phase 2: detailed sampling",
    "report_sections": {
        "location_and_geography": "...",
        "sampling_methodology": "...",
        "analytical_results": "...",
        "geological_interpretation": "...",
        "market_analysis": "...",
        "compliance_status": "...",
        "recommendations": "...",
        "disclaimer": "..."
    },
    "needs_refinement": false
}

Rules:
1. Write for non-technical investors — avoid jargon, explain terms
2. All numbers must match source data exactly — no fabrication
3. Recommendation must be actionable: "Proceed to...", "Conduct...", "Do not proceed..."
4. Risk summary: 3-5 specific risks with mitigation strategies
5. needs_refinement = true if missing data, contradictions, or unclear findings
6. Each section: 2-5 paragraphs
7. Return ONLY valid JSON, no markdown fences"""


def _build_prompt(state: dict[str, Any]) -> str:
    analysis = state.get("analysis_result", {})
    geology = state.get("geology_result", {})
    market = state.get("market_result", {})
    sampling = state.get("sampling_result", {})
    location = state.get("location", {})
    refinement_count = state.get("refinement_count", 0)

    return f"""REPORT GENERATION REQUEST

=== LOCATION ===
Region: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
GPS: ({location.get('lat', 'N/A')}, {location.get('lon', 'N/A')})
Area: {location.get('area_hectares', 'unknown')} hectares

=== ANALYSIS RESULTS ===
Dominant mineral: {analysis.get('dominant_mineral', 'unknown')}
Confidence: {analysis.get('overall_confidence', 0):.0%}
Rock type: {analysis.get('rock_type', 'unknown')}
Alteration: {analysis.get('alteration_type', 'unknown')}
Minerals: {json.dumps(analysis.get('minerals', []), indent=2)}

=== GEOLOGICAL CONTEXT ===
Belt: {geology.get('belt_name', 'unknown')}
Formation: {geology.get('formation', 'unknown')}
Deposit model: {geology.get('deposit_model', 'unknown')}
Structural setting: {geology.get('structural_setting', 'unknown')}
Resource potential: {geology.get('resource_potential', 'unknown')}
Pathfinder interpretation: {geology.get('pathfinder_interpretation', 'N/A')}
Comparable deposits: {json.dumps(geology.get('comparable_deposits', []))}

=== MARKET DATA ===
Gold price: ${market.get('gold_price_usd_oz', 0):,.2f}/oz
Copper price: ${market.get('copper_price_usd_lb', 0):,.2f}/lb
Trend: {market.get('commodity_trend', 'unknown')}
Deposit value: ${market.get('deposit_value_estimate_usd', 0):,.2f} NPV
Cut-off grade: {market.get('cut_off_grade_gpt', 0):.2f} g/t
Royalty rate: {market.get('royalty_rate_pct', 5)}%

=== SAMPLING STRATEGY ===
Strategy: {sampling.get('sampling_strategy', 'unknown')}
Grid spacing: {sampling.get('grid_spacing_m', 'unknown')}m
Waypoints: {len(sampling.get('waypoints', []))}
Estimated samples: {sampling.get('estimated_sample_count', 'unknown')}

=== REFINEMENT COUNT: {refinement_count} ===

Generate a comprehensive investor-ready report."""


def _build_html(result: dict[str, Any], analysis_id: str) -> str:
    """Build HTML report from structured sections."""
    sections = result.get("report_sections", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = [
        "<!DOCTYPE html><html><head>",
        "<meta charset='utf-8'>",
        "<style>",
        "body{font-family:Georgia,serif;max-width:800px;margin:0 auto;padding:20px;color:#333}",
        "h1{color:#1a5632;border-bottom:2px solid #2d7a4f;padding-bottom:10px}",
        "h2{color:#2d7a4f;border-bottom:1px solid #ccc;padding-bottom:5px}",
        ".highlight{background:#f0f7f0;padding:12px;border-left:4px solid #2d7a4f;margin:10px 0}",
        ".risk{background:#fff3f3;padding:12px;border-left:4px solid #c0392b;margin:10px 0}",
        "table{border-collapse:collapse;width:100%;margin:10px 0}",
        "td,th{border:1px solid #ddd;padding:8px;text-align:left}",
        "th{background:#f5f5f5}",
        ".meta{color:#666;font-size:0.9em}",
        "</style></head><body>",
        "<h1>AfriMine AI — Mineral Analysis Report</h1>",
        f"<p class='meta'>Generated: {now} | Analysis ID: {analysis_id}</p>",
        f"<h2>Executive Summary</h2><div class='highlight'>{result.get('executive_summary', '')}</div>",
    ]

    section_titles = {
        "location_and_geography": "Location & Geography",
        "sampling_methodology": "Sampling Methodology",
        "analytical_results": "Analytical Results",
        "geological_interpretation": "Geological Interpretation",
        "market_analysis": "Market Analysis & Valuation",
        "compliance_status": "Compliance Status",
        "recommendations": "Recommendations",
        "disclaimer": "Disclaimer",
    }

    for key, title in section_titles.items():
        content = sections.get(key, "")
        if content:
            html.append(f"<h2>{title}</h2><p>{content}</p>")

    findings = result.get("key_findings", [])
    if findings:
        html.append("<h2>Key Findings</h2><ul>")
        for f in findings:
            html.append(f"<li>{f}</li>")
        html.append("</ul>")

    risks = result.get("risk_summary", [])
    if risks:
        html.append("<h2>Risk Assessment</h2><div class='risk'><ul>")
        for r in risks:
            html.append(f"<li>{r}</li>")
        html.append("</ul></div>")

    html.append("</body></html>")
    return "\n".join(html)


async def report_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Report Agent node function.

    Synthesizes all agent outputs into an investor-ready report.
    Supports iterative refinement (max 3 loops).
    """
    analysis_id = state.get("analysis_id", "unknown")
    refinement_count = state.get("refinement_count", 0)
    logger.info(f"[{analysis_id}] Report Agent starting (refinement #{refinement_count})")

    if not rate_limiter.check("report"):
        return {
            "report_result": {
                "executive_summary": "Report generation rate limited",
                "needs_refinement": True,
                "report_version": refinement_count + 1,
            },
            "refinement_count": refinement_count + 1,
            "current_step": "compliance",
            "errors": ["Report Agent rate limited"],
        }

    rate_limiter.record("report")

    try:
        result = await retry_with_backoff(
            llm_json_call,
            SYSTEM_PROMPT,
            _build_prompt(state),
            temperature=0.4,
            max_output_tokens=8192,
        )

        result["report_version"] = refinement_count + 1
        result["report_html"] = _build_html(result, analysis_id)

        # Sanitize executive summary
        if result.get("executive_summary"):
            sanitized = sanitize_output(result["executive_summary"], "report")
            result["executive_summary"] = sanitized.output

        # Check refinement
        needs_refinement = result.get("needs_refinement", False) and refinement_count < settings.MAX_REFINEMENT_LOOPS
        result["needs_refinement"] = needs_refinement

        logger.info(
            f"[{analysis_id}] Report complete: v{result.get('report_version')}, "
            f"refinement_needed={needs_refinement}"
        )

        return {
            "report_result": result,
            "refinement_count": refinement_count + 1,
            "current_step": "compliance" if not needs_refinement else "analysis",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Report v{result.get('report_version')} complete. "
                        f"{'Needs refinement' if needs_refinement else 'Ready for compliance'}."
                    ),
                }
            ],
        }

    except Exception as e:
        error_msg = f"Report Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "report_result": {
                "executive_summary": "Report generation failed — manual review required.",
                "key_findings": [],
                "risk_summary": ["Automated report generation failed"],
                "recommendation": "Manual review by qualified geologist",
                "needs_refinement": True,
                "report_version": refinement_count + 1,
            },
            "refinement_count": refinement_count + 1,
            "current_step": "compliance",
            "errors": [error_msg],
        }
