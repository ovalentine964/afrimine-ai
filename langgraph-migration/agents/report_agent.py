"""
AfriMine AI — Report Agent
============================

Role: Generate investor-ready reports by synthesizing all agent outputs
      into structured HTML suitable for PDF conversion.

When it runs: After BOTH Geology and Market agents complete (fan-in).
What it reads: analysis_result, geology_result, market_result, sampling_result, location.
What it writes: report_result.

Architecture notes:
- This is the fan-in node — it waits for both parallel branches
- Uses NVIDIA NIM (MiniMax M3) for report generation
- Supports iterative refinement: if report quality is low, sets
  needs_refinement=True which loops back through Analysis
- Max refinement iterations: 3 (controlled by graph.py routing)
- Report uses Jinja2 templates for consistent formatting
- HTML output is converted to PDF by the Go backend (reportlab)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

REPORT_SYSTEM_PROMPT = """You are the Report Agent for AfriMine AI.

Your job: Synthesize all analysis results into an investor-ready technical report.
This report will be read by mining investors, government regulators, and geologists.

Return a JSON object with these exact keys:
{
    "executive_summary": "2-3 paragraph overview of findings...",
    "key_findings": [
        "Gold-bearing quartz vein identified with 82% confidence",
        "Grade estimate: 5.2 g/t Au (above cut-off of 1.8 g/t)",
        ...
    ],
    "risk_summary": [
        "Single sample — requires confirmation drilling",
        "No JORC-compliant resource estimate yet",
        ...
    ],
    "recommendation": "Proceed to Phase 2: detailed sampling and trenching",
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
1. Write for a non-technical investor audience — avoid jargon, explain terms
2. All numbers must match the source data exactly — no fabrication
3. Include the 28:1 exploitation ratio context (1M KES vs 28M+ KES value)
4. Recommendation must be actionable: "Proceed to...", "Conduct...", "Do not proceed..."
5. Risk summary must list 3-5 specific risks with mitigation strategies
6. needs_refinement = true if: missing data, contradictions, or unclear findings
7. Return ONLY valid JSON, no markdown fences
8. Report sections must each be 2-5 paragraphs"""


async def report_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Report Agent node function.

    Synthesizes all agent outputs into an investor-ready report.

    Args:
        state: The current AfriMineState.

    Returns:
        Partial state update with report_result.
    """
    analysis_id = state.get("analysis_id", "unknown")
    refinement_count = state.get("refinement_count", 0)
    logger.info(
        f"[{analysis_id}] Report Agent starting "
        f"(fan-in, refinement #{refinement_count})"
    )

    try:
        # NVIDIA NIM via OpenAI-compatible API (fallback: Groq → Mistral → Ollama)
        from llm_provider import get_llm_with_fallback
        llm, _provider = get_llm_with_fallback(
            temperature=0.4,  # Slightly higher for narrative writing
            max_tokens=8192,
        )

        # Gather all upstream results
        analysis = state.get("analysis_result", {})
        geology = state.get("geology_result", {})
        market = state.get("market_result", {})
        sampling = state.get("sampling_result", {})
        location = state.get("location", {})
        compliance = state.get("compliance_result", {})

        user_prompt = f"""REPORT GENERATION REQUEST

=== LOCATION ===
Region: {location.get('region', 'Unknown')}, {location.get('county', 'Migori')}, Kenya
GPS: ({location.get('lat', 'N/A')}, {location.get('lon', 'N/A')})
Area: {location.get('area_hectares', 'unknown')} hectares

=== ANALYSIS RESULTS ===
Dominant mineral: {analysis.get('dominant_mineral', 'unknown')}
Confidence: {analysis.get('overall_confidence', 0):.0%}
Rock type: {analysis.get('rock_type', 'unknown')}
Alteration: {analysis.get('alteration_type', 'unknown')}
Minerals found: {json.dumps(analysis.get('minerals', []), indent=2)}

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
Deposit value estimate: ${market.get('deposit_value_estimate_usd', 0):,.2f} NPV
Cut-off grade: {market.get('cut_off_grade_gpt', 0):.2f} g/t
Royalty rate: {market.get('royalty_rate_pct', 5)}%

=== SAMPLING STRATEGY ===
Strategy: {sampling.get('sampling_strategy', 'unknown')}
Grid spacing: {sampling.get('grid_spacing_m', 'unknown')}m
Waypoints: {len(sampling.get('waypoints', []))} points
Estimated samples: {sampling.get('estimated_sample_count', 'unknown')}

=== PREVIOUS REFINEMENT COUNT: {refinement_count} ===

Generate a comprehensive investor-ready report. Ensure all sections are complete and consistent."""

        response = await llm.ainvoke([
            SystemMessage(content=REPORT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)
        result["report_version"] = refinement_count + 1

        # Build HTML from sections
        sections = result.get("report_sections", {})
        html_parts = [
            "<!DOCTYPE html><html><head>",
            "<meta charset='utf-8'>",
            "<style>body{font-family:serif;max-width:800px;margin:0 auto;padding:20px}",
            "h1{color:#1a5632}h2{color:#2d7a4f;border-bottom:1px solid #ccc}",
            ".highlight{background:#f0f7f0;padding:10px;border-left:3px solid #2d7a4f}",
            ".risk{background:#fff3f3;padding:10px;border-left:3px solid #c0392b}",
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}",
            "</style></head><body>",
            "<h1>AfriMine AI — Mineral Analysis Report</h1>",
            f"<p><em>Generated: {{timestamp}} | Analysis ID: {analysis_id}</em></p>",
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
                html_parts.append(f"<h2>{title}</h2><p>{content}</p>")

        # Key findings
        findings = result.get("key_findings", [])
        if findings:
            html_parts.append("<h2>Key Findings</h2><ul>")
            for f in findings:
                html_parts.append(f"<li>{f}</li>")
            html_parts.append("</ul>")

        # Risks
        risks = result.get("risk_summary", [])
        if risks:
            html_parts.append("<h2>Risk Assessment</h2><div class='risk'><ul>")
            for r in risks:
                html_parts.append(f"<li>{r}</li>")
            html_parts.append("</ul></div>")

        html_parts.append("</body></html>")
        result["report_html"] = "\n".join(html_parts)

        # Check if refinement is needed (and we haven't exceeded max)
        needs_refinement = result.get("needs_refinement", False) and refinement_count < 3
        result["needs_refinement"] = needs_refinement

        logger.info(
            f"[{analysis_id}] Report Agent complete: "
            f"version={result.get('report_version')}, "
            f"refinement_needed={needs_refinement}"
        )

        return {
            "report_result": result,
            "refinement_count": refinement_count + 1,
            "current_step": "compliance" if not needs_refinement else "analysis",
            "messages": [
                HumanMessage(
                    content=f"Report v{result.get('report_version')} complete. "
                            f"{'Needs refinement' if needs_refinement else 'Ready for compliance check'}.",
                    name="report_agent",
                )
            ],
        }

    except json.JSONDecodeError as e:
        error_msg = f"Report Agent failed to parse LLM response: {e}"
        logger.error(f"[{analysis_id}] {error_msg}")
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

    except Exception as e:
        error_msg = f"Report Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "report_result": {},
            "refinement_count": refinement_count + 1,
            "current_step": "compliance",
            "errors": [error_msg],
        }
