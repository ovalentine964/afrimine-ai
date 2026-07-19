"""
AfriMine AI — Integration Test Fixtures
=========================================

Shared fixtures for all integration tests.
Uses in-memory checkpointer and mocked LLM calls for deterministic testing.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the agents source to path
AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src", "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)


# ---------------------------------------------------------------------------
# Mock LLM responses (deterministic, no API key needed)
# ---------------------------------------------------------------------------

MOCK_SAMPLING_RESULT = {
    "waypoints": [
        {"latitude": -1.05, "longitude": 34.55, "elevation_m": 1450, "rationale": "River confluence"},
        {"latitude": -1.06, "longitude": 34.56, "elevation_m": 1480, "rationale": "Fault intersection"},
        {"latitude": -1.04, "longitude": 34.54, "elevation_m": 1420, "rationale": "Color anomaly"},
    ],
    "field_route": [
        {"latitude": -1.05, "longitude": 34.55, "order": 1},
        {"latitude": -1.04, "longitude": 34.54, "order": 2},
        {"latitude": -1.06, "longitude": 34.56, "order": 3},
    ],
    "grid_spacing_m": 50,
    "sampling_strategy": "grid",
    "rationale": "Grid sampling over anomalous area with 50m spacing",
    "estimated_sample_count": 12,
}

MOCK_ANALYSIS_RESULT = {
    "minerals": [
        {
            "mineral_name": "Gold-bearing quartz",
            "confidence": 0.85,
            "grade_estimate_ppm": 5.2,
            "grade_estimate_gpt": 5.2,
            "visual_indicators": ["sulfide veining", "quartz veining", "iron staining"],
            "pathfinder_elements": {"As": 120.5, "Bi": 8.3},
        }
    ],
    "dominant_mineral": "Gold-bearing quartz",
    "overall_confidence": 0.82,
    "rock_type": "quartz vein",
    "alteration_type": "silicification",
    "xrf_data": {"Au": 5.2, "Ag": 2.1, "Cu": 45, "As": 120.5, "Fe": 3.2, "Bi": 8.3},
    "image_analysis_notes": "Quartz veining with sulfide staining visible",
    "requires_geology_context": True,
}

MOCK_GEOLOGY_RESULT = {
    "belt_name": "Migori Greenstone Belt",
    "formation": "Nyanzian System",
    "structural_setting": "NNW-trending shear zone",
    "deposit_model": "orogenic gold",
    "pathfinder_interpretation": "As at 120 ppm strongly indicates gold mineralization",
    "alteration_mapping": {"silicification": "B11/B12 ratio suggests silica enrichment"},
    "resource_potential": "high",
    "comparable_deposits": ["Macalder mine", "Nyatike goldfields"],
    "recommendations": "Proceed with detailed sampling along NNW shear zone",
}

MOCK_MARKET_RESULT = {
    "gold_price_usd_oz": 2350.0,
    "copper_price_usd_lb": 4.20,
    "commodity_trend": "stable",
    "deposit_value_estimate_usd": 125000.0,
    "cut_off_grade_gpt": 1.52,
    "recovery_rate_assumption": 0.85,
    "royalty_rate_pct": 5.0,
    "market_risk_factors": [],
    "valuation_notes": "Gold at $2,350/oz. Deposit value: $125,000 NPV",
}

MOCK_REPORT_RESULT = {
    "executive_summary": "Gold-bearing quartz vein identified in Nyatike with 5.2 g/t grade.",
    "key_findings": ["Gold at 5.2 g/t", "Orogenic gold deposit model", "High resource potential"],
    "risk_summary": ["Artisanal mining competition", "Infrastructure limitations"],
    "recommendation": "Proceed to Phase 2: detailed sampling along NNW shear zone",
    "report_sections": {
        "location_and_geography": "Nyatike, Migori County, Kenya",
        "analytical_results": "Gold at 5.2 g/t with 82% confidence",
        "geological_interpretation": "Orogenic gold in Migori Greenstone Belt",
        "market_analysis": "Deposit value $125,000 NPV",
        "compliance_status": "Prospecting License required",
        "recommendations": "Proceed with detailed sampling",
        "disclaimer": "This report is for informational purposes only",
    },
    "needs_refinement": False,
    "report_version": 1,
}

MOCK_COMPLIANCE_RESULT = {
    "license_type_required": "Prospecting License",
    "license_status": "not_held",
    "eia_required": True,
    "eia_status": "not_submitted",
    "royalty_percentage": 5.0,
    "community_agreement_required": True,
    "compliance_issues": ["No PL held", "EIA not submitted"],
    "regulatory_recommendations": ["Apply for PL at DGS Kisumu", "Engage NEMA EIA firm"],
    "is_compliant": False,
}


def _make_llm_response(content: str) -> MagicMock:
    """Create a mock LLM response object."""
    response = MagicMock()
    response.content = content
    return response


def _mock_llm_json_call(system_prompt: str, user_prompt: str, **kwargs) -> dict:
    """Determine which agent is calling and return appropriate mock result."""
    prompt_lower = system_prompt.lower()
    if "sampling" in prompt_lower:
        return MOCK_SAMPLING_RESULT.copy()
    elif "analysis" in prompt_lower or "analyz" in prompt_lower:
        return MOCK_ANALYSIS_RESULT.copy()
    elif "geolog" in prompt_lower:
        return MOCK_GEOLOGY_RESULT.copy()
    elif "report" in prompt_lower:
        return MOCK_REPORT_RESULT.copy()
    elif "compliance" in prompt_lower or "kenya mining" in prompt_lower:
        return MOCK_COMPLIANCE_RESULT.copy()
    return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nyatike_location() -> dict[str, Any]:
    """Standard Nyatike, Migori County location."""
    return {
        "lat": -1.05,
        "lon": 34.55,
        "region": "Nyatike",
        "county": "Migori",
        "country": "Kenya",
        "area_hectares": 10,
    }


@pytest.fixture
def gold_sample_data() -> dict[str, Any]:
    """Gold-bearing quartz sample with XRF data."""
    return {
        "sample_id": "NYA-TEST-001",
        "xrf_readings": {"Au": 5.2, "Ag": 2.1, "Cu": 45, "As": 120.5, "Fe": 3.2, "Bi": 8.3},
        "notes": "Quartz vein with sulfide staining near river bed",
        "preliminary_result": "Gold-bearing quartz",
    }


@pytest.fixture
def base_state(nyatike_location, gold_sample_data) -> dict[str, Any]:
    """Complete initial state for pipeline execution."""
    return {
        "analysis_id": str(uuid.uuid4()),
        "user_id": "test-user-001",
        "location": nyatike_location,
        "sample_data": gold_sample_data,
        "satellite_imagery": "",
        "sampling_result": {},
        "analysis_result": {},
        "geology_result": {},
        "market_result": {},
        "report_result": {},
        "compliance_result": {},
        "messages": [],
        "current_step": "sampling",
        "errors": [],
        "metadata": {},
        "refinement_count": 0,
    }


@pytest.fixture
def mock_llm():
    """Mock all LLM calls to return deterministic results."""
    with patch("agents.base.llm_json_call", new_callable=AsyncMock) as mock:
        mock.side_effect = _mock_llm_json_call
        yield mock


@pytest.fixture
def mock_rate_limiter():
    """Disable rate limiting for tests."""
    with patch("security.middleware.rate_limiter") as mock:
        mock.check.return_value = True
        mock.record.return_value = None
        yield mock


@pytest.fixture
def in_memory_checkpointer():
    """Create an in-memory LangGraph checkpointer."""
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
