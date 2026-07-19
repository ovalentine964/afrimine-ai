"""
AfriMine AI — Production State Schema
=======================================

TypedDict-based state with validation helpers, safe defaults, and type safety.
Flows through the 6-agent pipeline:

    Sampling → Analysis ──┬→ Geology ──┬→ Report → Compliance
                          │            │
                          └→ Market ───┘

Design:
- TypedDict (not Pydantic) for LangGraph native compatibility
- Annotated[list, add_messages] for append-only message history
- operator.add for error accumulation (never silently drops)
- Validation functions for GPS bounds, confidence ranges, etc.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


# NOTE: All agents return plain dicts {"role": ..., "content": ...}.
# add_messages works with both LangChain BaseMessage objects and plain dicts,
# so we keep it for LangGraph compatibility. If issues arise, replace with:
#   messages: Annotated[list, operator.add]


# ---------------------------------------------------------------------------
# Sub-schemas: structured outputs per agent
# ---------------------------------------------------------------------------

class GPSPoint(TypedDict, total=False):
    """A single GPS coordinate with metadata."""
    latitude: float
    longitude: float
    elevation_m: float
    accuracy_m: float
    timestamp: str  # ISO 8601


class SamplingResult(TypedDict, total=False):
    """Output from the Sampling Agent."""
    waypoints: list[GPSPoint]
    field_route: list[GPSPoint]
    grid_spacing_m: float
    sampling_strategy: str
    rationale: str
    estimated_sample_count: int


class MineralClassification(TypedDict, total=False):
    """A single mineral identified in the analysis."""
    mineral_name: str
    confidence: float
    grade_estimate_ppm: float
    grade_estimate_gpt: float
    visual_indicators: list[str]
    pathfinder_elements: dict[str, float]


class AnalysisResult(TypedDict, total=False):
    """Output from the Analysis Agent (Gemini Vision)."""
    minerals: list[MineralClassification]
    dominant_mineral: str
    overall_confidence: float
    rock_type: str
    alteration_type: str
    xrf_data: dict[str, float]
    image_analysis_notes: str
    requires_geology_context: bool


class GeologicalContext(TypedDict, total=False):
    """Output from the Geology Agent."""
    belt_name: str
    formation: str
    structural_setting: str
    deposit_model: str
    pathfinder_interpretation: str
    alteration_mapping: dict[str, str]
    resource_potential: Literal["high", "medium", "low", "insufficient_data"]
    comparable_deposits: list[str]
    recommendations: str


class MarketResult(TypedDict, total=False):
    """Output from the Market Agent."""
    gold_price_usd_oz: float
    copper_price_usd_lb: float
    commodity_trend: Literal["bullish", "bearish", "stable"]
    deposit_value_estimate_usd: float
    cut_off_grade_gpt: float
    recovery_rate_assumption: float
    royalty_rate_pct: float
    market_risk_factors: list[str]
    valuation_notes: str


class ReportResult(TypedDict, total=False):
    """Output from the Report Agent."""
    report_html: str
    report_sections: dict[str, str]
    executive_summary: str
    key_findings: list[str]
    risk_summary: list[str]
    recommendation: str
    pdf_url: str
    report_version: int
    needs_refinement: bool


class ComplianceResult(TypedDict, total=False):
    """Output from the Compliance Agent (Kenya Mining Act 2016)."""
    license_type_required: str
    license_status: Literal["valid", "expired", "not_held", "not_applicable"]
    eia_required: bool
    eia_status: Literal["approved", "pending", "not_submitted", "not_required"]
    royalty_percentage: float
    community_agreement_required: bool
    compliance_issues: list[str]
    regulatory_recommendations: list[str]
    is_compliant: bool


# ---------------------------------------------------------------------------
# Main State Schema
# ---------------------------------------------------------------------------

class AfriMineState(TypedDict, total=False):
    """
    The shared state for the AfriMine 6-agent LangGraph pipeline.

    LangGraph uses this to:
    1. Initialize the graph with input data
    2. Pass intermediate results between nodes
    3. Checkpoint state to Supabase for crash recovery
    4. Stream partial results to the Flutter frontend
    """

    # ── Input ──────────────────────────────────────────────────────────────
    location: dict[str, Any]
    sample_data: dict[str, Any]
    satellite_imagery: str
    user_id: str
    analysis_id: str

    # ── Agent Outputs ──────────────────────────────────────────────────────
    sampling_result: SamplingResult
    analysis_result: AnalysisResult
    geology_result: GeologicalContext
    market_result: MarketResult
    report_result: ReportResult
    compliance_result: ComplianceResult

    # ── Shared Control Flow ────────────────────────────────────────────────
    messages: Annotated[list, add_messages]
    current_step: str
    errors: Annotated[list[str], operator.add]
    metadata: dict[str, Any]

    # ── Routing Control ────────────────────────────────────────────────────
    routing_decision: Literal["parallel_geo_market", "market_only", "direct_report"]
    refinement_count: int


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

KENYA_LAT_RANGE = (-5.0, 5.0)
KENYA_LON_RANGE = (34.0, 42.0)
MIGORI_LAT_RANGE = (-1.5, -0.8)
MIGORI_LON_RANGE = (34.2, 35.0)


def validate_gps(lat: float, lon: float, strict: bool = False) -> bool:
    """Check if GPS coordinates are within Kenya (or Migori if strict)."""
    lat_range = MIGORI_LAT_RANGE if strict else KENYA_LAT_RANGE
    lon_range = MIGORI_LON_RANGE if strict else KENYA_LON_RANGE
    return lat_range[0] <= lat <= lat_range[1] and lon_range[0] <= lon <= lon_range[1]


def clamp_gps(lat: float, lon: float) -> tuple[float, float]:
    """Clamp GPS coordinates to Kenya bounds."""
    return (
        max(KENYA_LAT_RANGE[0], min(KENYA_LAT_RANGE[1], lat)),
        max(KENYA_LON_RANGE[0], min(KENYA_LON_RANGE[1], lon)),
    )


def validate_confidence(value: float) -> bool:
    """Confidence must be 0.0–1.0."""
    return 0.0 <= value <= 1.0


def validate_state_inputs(state: dict[str, Any]) -> list[str]:
    """
    Validate required input fields in state before pipeline execution.
    Returns list of validation errors (empty = valid).
    """
    errors = []

    if not state.get("analysis_id"):
        errors.append("Missing required field: analysis_id")

    if not state.get("user_id"):
        errors.append("Missing required field: user_id")

    location = state.get("location", {})
    if not location.get("lat") or not location.get("lon"):
        errors.append("Missing required field: location.lat/lon")
    elif not validate_gps(location["lat"], location["lon"]):
        errors.append(
            f"GPS ({location['lat']}, {location['lon']}) outside Kenya bounds"
        )

    sample = state.get("sample_data", {})
    if not sample.get("sample_id"):
        errors.append("Missing required field: sample_data.sample_id")

    return errors


def build_initial_state(
    analysis_id: str,
    user_id: str,
    location: dict[str, Any],
    sample_data: dict[str, Any],
    satellite_imagery: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a valid initial state dict for pipeline invocation.
    Applies defaults for all optional fields.
    """
    return {
        # Input
        "analysis_id": analysis_id,
        "user_id": user_id,
        "location": location,
        "sample_data": sample_data,
        "satellite_imagery": satellite_imagery,
        # Agent outputs (empty defaults)
        "sampling_result": {},
        "analysis_result": {},
        "geology_result": {},
        "market_result": {},
        "report_result": {},
        "compliance_result": {},
        # Control flow
        "messages": [],
        "current_step": "sampling",
        "errors": [],
        "metadata": metadata or {},
        "refinement_count": 0,
    }
