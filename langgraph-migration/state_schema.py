"""
AfriMine AI — State Schema for LangGraph 1.0
=============================================

Defines the shared state that flows through the 6-agent pipeline:

    Sampling → Analysis ──┬→ Geology ──┬→ Report → Compliance
                          │            │
                          └→ Market ───┘

Design decisions:
- TypedDict (not Pydantic BaseModel) for LangGraph native compatibility
- Annotated[list, add_messages] for append-only message history
- Per-agent output fields with explicit types for type safety
- Metadata dict for flexible extension without schema changes
- Errors list accumulates across agents (never silently drops)
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


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
    waypoints: list[GPSPoint]           # Recommended follow-up sample points
    field_route: list[GPSPoint]          # Optimized walking route
    grid_spacing_m: float                # Recommended grid cell size
    sampling_strategy: str               # e.g. "grid", "transect", "bias"
    rationale: str                       # Why this layout
    estimated_sample_count: int


class MineralClassification(TypedDict, total=False):
    """A single mineral identified in the analysis."""
    mineral_name: str                    # e.g. "Gold-bearing quartz"
    confidence: float                    # 0.0–1.0
    grade_estimate_ppm: float            # Parts per million
    grade_estimate_gpt: float            # Grams per tonne
    visual_indicators: list[str]         # e.g. ["veining", "oxidation", "sulfide"]
    pathfinder_elements: dict[str, float]  # e.g. {"As": 120.5, "Bi": 8.3}


class AnalysisResult(TypedDict, total=False):
    """Output from the Analysis Agent (Gemini Vision)."""
    minerals: list[MineralClassification]
    dominant_mineral: str
    overall_confidence: float
    rock_type: str                       # e.g. "quartz vein", "laterite"
    alteration_type: str                 # e.g. "silicification", "sericitization"
    xrf_data: dict[str, float]          # Raw XRF element concentrations
    image_analysis_notes: str            # Gemini's visual reasoning
    requires_geology_context: bool       # Flag for conditional routing


class GeologicalContext(TypedDict, total=False):
    """Output from the Geology Agent."""
    belt_name: str                       # e.g. "Migori Greenstone Belt"
    formation: str                       # e.g. "Nyanzian System"
    structural_setting: str              # e.g. "fold hinge zone"
    deposit_model: str                   # e.g. "orogenic gold", "VMS"
    pathfinder_interpretation: str       # As→Au correlation narrative
    alteration_mapping: dict[str, str]   # Band ratio → alteration type
    resource_potential: Literal["high", "medium", "low", "insufficient_data"]
    comparable_deposits: list[str]       # Known similar deposits
    recommendations: str                 # Geological advice for next steps


class MarketResult(TypedDict, total=False):
    """Output from the Market Agent."""
    gold_price_usd_oz: float
    copper_price_usd_lb: float
    commodity_trend: Literal["bullish", "bearish", "stable"]
    deposit_value_estimate_usd: float    # NPV-based rough estimate
    cut_off_grade_gpt: float             # Economic cut-off grade
    recovery_rate_assumption: float      # e.g. 0.85 for gravity+cyanide
    royalty_rate_pct: float              # Kenya mining royalty rate
    market_risk_factors: list[str]
    valuation_notes: str


class ReportResult(TypedDict, total=False):
    """Output from the Report Agent (investor PDF)."""
    report_html: str                     # Rendered HTML for PDF conversion
    report_sections: dict[str, str]      # Section name → content
    executive_summary: str
    key_findings: list[str]
    risk_summary: list[str]
    recommendation: str                  # e.g. "Proceed to Phase 2 drilling"
    pdf_url: str                         # Supabase storage URL after upload
    report_version: int                  # For refinement loop tracking
    needs_refinement: bool               # Flag for iterative loop


class ComplianceResult(TypedDict, total=False):
    """Output from the Compliance Agent (Kenya Mining Act 2016)."""
    license_type_required: str           # e.g. "Prospecting License"
    license_status: Literal["valid", "expired", "not_held", "not_applicable"]
    eia_required: bool                   # Environmental Impact Assessment
    eia_status: Literal["approved", "pending", "not_submitted", "not_required"]
    royalty_percentage: float
    community_agreement_required: bool
    compliance_issues: list[str]         # Any blocking issues
    regulatory_recommendations: list[str]
    is_compliant: bool                   # Final pass/fail


# ---------------------------------------------------------------------------
# Main State Schema — flows through the entire graph
# ---------------------------------------------------------------------------

class AfriMineState(TypedDict, total=False):
    """
    The shared state for the AfriMine 6-agent LangGraph pipeline.

    This TypedDict is the single source of truth for all data flowing
    between agents. LangGraph uses it to:
    1. Initialize the graph with input data
    2. Pass intermediate results between nodes
    3. Checkpoint state to Supabase for crash recovery
    4. Stream partial results to the Flutter frontend

    Field naming convention:
    - Input fields: no prefix (location, sample_data, etc.)
    - Agent outputs: <agent>_result (sampling_result, analysis_result, etc.)
    - Shared control: messages, current_step, errors, metadata
    """

    # ── Input ──────────────────────────────────────────────────────────────
    location: dict[str, Any]
    """GPS coordinates and region info. Keys: lat, lon, region, county, country."""

    sample_data: dict[str, Any]
    """Mineral sample metadata. Keys: sample_id, photo_url, xrf_readings, notes."""

    satellite_imagery: str
    """Base64-encoded or URL to Sentinel-2 tile for the location."""

    user_id: str
    """Supabase auth user ID for the requesting user."""

    analysis_id: str
    """Unique ID for this analysis run (UUID)."""

    # ── Agent Outputs ──────────────────────────────────────────────────────
    sampling_result: SamplingResult
    """GPS waypoints and field routes from the Sampling Agent."""

    analysis_result: AnalysisResult
    """Mineral classification and grade estimates from the Analysis Agent."""

    geology_result: GeologicalContext
    """Geological interpretation from the Geology Agent."""

    market_result: MarketResult
    """Market prices and deposit valuation from the Market Agent."""

    report_result: ReportResult
    """Investor report content from the Report Agent."""

    compliance_result: ComplianceResult
    """Regulatory compliance check from the Compliance Agent."""

    # ── Shared Control Flow ────────────────────────────────────────────────
    messages: Annotated[list, add_messages]
    """Append-only message log for agent-to-agent communication and user-facing traces."""

    current_step: str
    """Name of the currently executing node (for observability)."""

    errors: Annotated[list[str], operator.add]
    """Accumulated error messages. Uses operator.add so each node appends, never overwrites."""

    metadata: dict[str, Any]
    """Flexible bag for timestamps, tracing IDs, model versions, etc."""

    # ── Routing Control ────────────────────────────────────────────────────
    routing_decision: Literal["parallel_geo_market", "market_only", "direct_report"]
    """Set by the conditional router after Analysis Agent completes."""

    refinement_count: int
    """How many times the Report Agent has looped back for refinement (max: 3)."""
