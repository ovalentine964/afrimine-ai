"""
AfriMine AI — MCP Server Definitions
=======================================

Model Context Protocol (MCP) servers expose agent tools as standardized
interfaces that any MCP-compatible client can discover and invoke.

Each AfriMine agent has associated MCP tools:
- Sampling:   gps_waypoint_generator, route_optimizer
- Analysis:   mineral_classifier, xrf_analyzer
- Geology:    deposit_model_lookup, pathfinder_analyzer, band_ratio_calculator
- Market:     price_fetcher, deposit_valuator, cut_off_calculator
- Report:     report_generator, pdf_converter
- Compliance: license_checker, eia_checker, royalty_calculator

Architecture notes:
- MCP servers run as separate processes (stdio or SSE transport)
- Tools are Python functions decorated with @tool
- LangGraph agents call tools via langchain's tool binding
- Future: expose MCP servers via A2A bridge for Go backend access
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ===========================================================================
# Sampling Agent Tools
# ===========================================================================

@tool
def gps_waypoint_generator(
    center_lat: float,
    center_lon: float,
    grid_spacing_m: int = 50,
    grid_size: int = 4,
    strategy: str = "grid",
) -> str:
    """
    Generate GPS waypoints for mineral sampling around a center point.

    Args:
        center_lat: Center latitude (WGS84, decimal degrees)
        center_lon: Center longitude (WGS84, decimal degrees)
        grid_spacing_m: Distance between waypoints in meters
        grid_size: Number of points per axis (grid_size x grid_size total)
        strategy: "grid", "transect", or "bias"

    Returns:
        JSON string with list of waypoints (lat, lon, elevation_m).
    """
    waypoints = []

    # 1 degree latitude ≈ 111,320 meters
    lat_offset = grid_spacing_m / 111_320.0
    # 1 degree longitude ≈ 111,320 * cos(latitude) meters
    lon_offset = grid_spacing_m / (111_320.0 * math.cos(math.radians(center_lat)))

    half = grid_size // 2

    for i in range(grid_size):
        for j in range(grid_size):
            lat = center_lat + (i - half) * lat_offset
            lon = center_lon + (j - half) * lon_offset

            if strategy == "bias":
                # Bias toward center — tighter spacing near the sample
                dist = math.sqrt((i - half) ** 2 + (j - half) ** 2)
                if dist > half * 0.7:
                    continue

            waypoints.append({
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "elevation_m": 0,  # Would need DEM lookup in production
                "order": len(waypoints) + 1,
            })

    return json.dumps({
        "waypoints": waypoints,
        "total_points": len(waypoints),
        "strategy": strategy,
        "grid_spacing_m": grid_spacing_m,
    })


@tool
def route_optimizer(waypoints_json: str) -> str:
    """
    Optimize walking route through waypoints using nearest-neighbor heuristic.

    Args:
        waypoints_json: JSON string with list of waypoints.

    Returns:
        JSON string with optimized route order.
    """
    data = json.loads(waypoints_json)
    waypoints = data if isinstance(data, list) else data.get("waypoints", [])

    if len(waypoints) <= 2:
        return json.dumps({"route": waypoints, "total_distance_m": 0})

    # Nearest-neighbor heuristic
    visited = [waypoints[0]]
    remaining = waypoints[1:]
    total_distance = 0.0

    while remaining:
        current = visited[-1]
        nearest_idx = 0
        nearest_dist = float("inf")

        for i, wp in enumerate(remaining):
            dlat = wp["latitude"] - current["latitude"]
            dlon = wp["longitude"] - current["longitude"]
            dist = math.sqrt(dlat**2 + dlon**2) * 111_320  # Approx meters
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = i

        total_distance += nearest_dist
        visited.append(remaining.pop(nearest_idx))

    return json.dumps({
        "route": [{"order": i + 1, **wp} for i, wp in enumerate(visited)],
        "total_distance_m": round(total_distance, 1),
    })


# ===========================================================================
# Analysis Agent Tools
# ===========================================================================

@tool
def xrf_analyzer(elements_json: str) -> str:
    """
    Analyze XRF readings and identify anomalous elements.

    Args:
        elements_json: JSON string with element concentrations (ppm or %).

    Returns:
        JSON string with anomaly flags and interpretations.
    """
    elements = json.loads(elements_json)

    # Thresholds for anomaly detection (Migori Belt specific)
    thresholds = {
        "Au": {"anomaly": 0.5, "high": 5.0, "unit": "ppm", "significance": "Gold mineralization"},
        "Ag": {"anomaly": 2.0, "high": 20.0, "unit": "ppm", "significance": "Silver association"},
        "Cu": {"anomaly": 200, "high": 1000, "unit": "ppm", "significance": "Copper mineralization (VMS)"},
        "As": {"anomaly": 50, "high": 200, "unit": "ppm", "significance": "Pathfinder for gold"},
        "Bi": {"anomaly": 5, "high": 20, "unit": "ppm", "significance": "Pathfinder for gold"},
        "Sb": {"anomaly": 10, "high": 50, "unit": "ppm", "significance": "Pathfinder for gold"},
        "Zn": {"anomaly": 500, "high": 2000, "unit": "ppm", "significance": "Zinc mineralization (VMS)"},
        "Pb": {"anomaly": 100, "high": 500, "unit": "ppm", "significance": "Lead association"},
        "Fe": {"anomaly": 5.0, "high": 15.0, "unit": "%", "significance": "Iron sulfide/oxide"},
        "S": {"anomaly": 1.0, "high": 5.0, "unit": "%", "significance": "Sulfide content"},
    }

    anomalies = []
    interpretations = []

    for element, value in elements.items():
        if element in thresholds:
            thresh = thresholds[element]
            if value >= thresh["high"]:
                anomalies.append({
                    "element": element,
                    "value": value,
                    "level": "HIGH",
                    "threshold": thresh["high"],
                    "significance": thresh["significance"],
                })
            elif value >= thresh["anomaly"]:
                anomalies.append({
                    "element": element,
                    "value": value,
                    "level": "anomaly",
                    "threshold": thresh["anomaly"],
                    "significance": thresh["significance"],
                })

    # Pathfinder interpretation
    as_val = elements.get("As", 0)
    au_val = elements.get("Au", 0)
    if as_val > 50 and au_val > 0.5:
        interpretations.append(
            f"As ({as_val} ppm) + Au ({au_val} ppm) correlation: "
            f"Strong indicator of orogenic gold system"
        )

    return json.dumps({
        "anomalies": anomalies,
        "interpretations": interpretations,
        "anomaly_count": len(anomalies),
        "has_gold_anomaly": any(a["element"] == "Au" for a in anomalies),
        "has_pathfinder_anomaly": any(a["element"] in ("As", "Bi", "Sb") for a in anomalies),
    })


# ===========================================================================
# Geology Agent Tools
# ===========================================================================

@tool
def deposit_model_lookup(belt_name: str, mineral_type: str) -> str:
    """
    Look up known deposit models for a geological belt and mineral type.

    Args:
        belt_name: Name of the geological belt (e.g., "Migori Greenstone Belt")
        mineral_type: Primary mineral of interest (e.g., "gold", "copper")

    Returns:
        JSON string with deposit model information.
    """
    # Knowledge base (production: Supabase pgvector store)
    models = {
        "Migori Greenstone Belt": {
            "gold": {
                "model": "Orogenic Gold",
                "host_rocks": ["quartz veins", "shear zones", "banded iron formation"],
                "pathfinder_elements": ["As", "Bi", "Sb", "Hg", "W"],
                "alteration": ["silicification", "sericitization", "carbonatization"],
                "structural_controls": ["NNW shear zones", "fold hinges", "fault intersections"],
                "typical_grades": "1-20 g/t Au (high-grade shoots: 30+ g/t)",
                "depth_range": "0-500m",
                "comparable_deposits": ["Macalder mine", "Nyatike goldfields", "Masara"],
                "exploration_methods": ["soil geochemistry", "trenching", "RC drilling", "ground magnetics"],
            },
            "copper": {
                "model": "Volcanogenic Massive Sulfide (VMS)",
                "host_rocks": ["mafic volcanics", "volcaniclastics", "exhalites"],
                "pathfinder_elements": ["Cu", "Zn", "Ba", "Ag", "Au"],
                "alteration": ["chlorite", "sericite", "silica"],
                "structural_controls": ["stratigraphic contacts", "synvolcanic faults"],
                "typical_grades": "0.5-3% Cu, 1-5% Zn",
                "depth_range": "0-300m",
                "comparable_deposits": ["Macalder Cu-Au", "Kisii copper occurrences"],
                "exploration_methods": ["VTEM", "IP survey", "diamond drilling"],
            },
        },
    }

    belt_models = models.get(belt_name, {})
    model = belt_models.get(mineral_type.lower())

    if not model:
        return json.dumps({
            "error": f"No deposit model found for {mineral_type} in {belt_name}",
            "available_belts": list(models.keys()),
        })

    return json.dumps({"belt": belt_name, "mineral": mineral_type, **model})


@tool
def band_ratio_calculator(b4: float, b2: float, b11: float, b12: float, b8a: float) -> str:
    """
    Calculate Sentinel-2 band ratios for alteration mapping.

    Args:
        b4: Band 4 (Red, 665nm)
        b2: Band 4 (Blue, 490nm)
        b11: Band 11 (SWIR, 1610nm)
        b12: Band 12 (SWIR, 2190nm)
        b8a: Band 8A (NIR narrow, 865nm)

    Returns:
        JSON string with band ratios and alteration interpretations.
    """
    ratios = {
        "B4_B2": round(b4 / b2, 3) if b2 > 0 else 0,  # Iron oxidation
        "B11_B12": round(b11 / b12, 3) if b12 > 0 else 0,  # Silicification
        "B8A_B4": round(b8a / b4, 3) if b4 > 0 else 0,  # Clay alteration
    }

    interpretations = []

    if ratios["B4_B2"] > 1.5:
        interpretations.append("Iron oxidation detected (gossan indicator) — potential mineralization")
    if ratios["B11_B12"] > 1.2:
        interpretations.append("Silicification detected — hydrothermal alteration")
    if ratios["B8A_B4"] > 1.1:
        interpretations.append("Clay alteration (sericite/kaolinite) — proximal alteration zone")

    return json.dumps({
        "ratios": ratios,
        "interpretations": interpretations,
        "alteration_detected": len(interpretations) > 0,
    })


# ===========================================================================
# Market Agent Tools
# ===========================================================================

@tool
def cut_off_calculator(
    operating_cost_usd_per_tonne: float,
    metal_price_usd_per_gram: float,
    recovery_rate: float,
) -> str:
    """
    Calculate the economic cut-off grade for mining.

    Args:
        operating_cost_usd_per_tonne: Total operating cost per tonne of ore
        metal_price_usd_per_gram: Current metal price per gram
        recovery_rate: Metallurgical recovery rate (0.0-1.0)

    Returns:
        JSON string with cut-off grade in g/t.
    """
    if metal_price_usd_per_gram <= 0 or recovery_rate <= 0:
        return json.dumps({"error": "Invalid inputs: price and recovery must be positive"})

    cut_off = operating_cost_usd_per_tonne / (metal_price_usd_per_gram * recovery_rate)

    return json.dumps({
        "cut_off_grade_gpt": round(cut_off, 2),
        "operating_cost": operating_cost_usd_per_tonne,
        "metal_price_per_gram": metal_price_usd_per_gram,
        "recovery_rate": recovery_rate,
        "interpretation": (
            f"Ore must grade above {cut_off:.2f} g/t to be economically viable "
            f"at current prices and costs."
        ),
    })


@tool
def deposit_valuator(
    grade_gpt: float,
    tonnage: float,
    gold_price_usd_oz: float,
    recovery_rate: float,
    discount_rate: float = 0.10,
    mine_life_years: int = 5,
) -> str:
    """
    Estimate deposit value using simplified DCF analysis.

    Args:
        grade_gpt: Average grade in grams per tonne
        tonnage: Estimated tonnes of ore
        gold_price_usd_oz: Current gold price in USD/oz
        recovery_rate: Metallurgical recovery rate
        discount_rate: Discount rate for NPV
        mine_life_years: Assumed mine life in years

    Returns:
        JSON string with NPV and annual cash flow estimates.
    """
    GOLD_OZ_TO_GRAMS = 31.1035
    gold_price_per_gram = gold_price_usd_oz / GOLD_OZ_TO_GRAMS

    contained_gold_g = grade_gpt * tonnage
    recoverable_gold_g = contained_gold_g * recovery_rate
    gross_value = recoverable_gold_g * gold_price_per_gram

    annual_value = gross_value / mine_life_years
    npv = sum(annual_value / (1 + discount_rate) ** y for y in range(1, mine_life_years + 1))

    return json.dumps({
        "npv_usd": round(npv, 2),
        "gross_value_usd": round(gross_value, 2),
        "annual_cash_flow_usd": round(annual_value, 2),
        "contained_gold_kg": round(contained_gold_g / 1000, 2),
        "recoverable_gold_kg": round(recoverable_gold_g / 1000, 2),
        "assumptions": {
            "grade_gpt": grade_gpt,
            "tonnage": tonnage,
            "gold_price_usd_oz": gold_price_usd_oz,
            "recovery_rate": recovery_rate,
            "discount_rate": discount_rate,
            "mine_life_years": mine_life_years,
        },
    })


# ===========================================================================
# Compliance Agent Tools
# ===========================================================================

@tool
def license_checker(license_type: str, area_hectares: float, activity: str) -> str:
    """
    Check which mining license is required based on activity and area.

    Args:
        license_type: Current license held (e.g., "none", "RP", "PL", "ML", "AMP")
        area_hectares: Size of the prospecting area
        activity: Type of activity ("survey", "sampling", "drilling", "extraction")

    Returns:
        JSON string with license requirements and recommendations.
    """
    requirements = {
        "survey": {
            "min_license": "Reconnaissance Permit (RP)",
            "fee_kes": 10_000,
            "max_area_km2": 1000,
            "duration": "1 year (renewable)",
        },
        "sampling": {
            "min_license": "Prospecting License (PL)",
            "fee_kes": 50_000,
            "max_area_km2": 50,
            "duration": "3 years (renewable twice)",
        },
        "drilling": {
            "min_license": "Prospecting License (PL)",
            "fee_kes": 50_000,
            "max_area_km2": 50,
            "duration": "3 years (renewable twice)",
        },
        "extraction": {
            "min_license": "Mining License (ML)",
            "fee_kes": 500_000,
            "max_area_km2": 50,
            "duration": "25 years (renewable)",
            "additional": ["EIA approved", "Mine Plan", "Financial assurance"],
        },
    }

    # Check for artisanal permit option
    if area_hectares <= 1 and activity == "extraction":
        return json.dumps({
            "required_license": "Artisanal Mining Permit (AMP)",
            "fee_kes": 2_000,
            "duration": "2 years (renewable)",
            "conditions": [
                "Kenyan citizen",
                "Member of mining cooperative",
                "Manual methods only (no mechanized processing)",
                "No mercury use (prohibited since 2019)",
            ],
            "current_license": license_type,
            "upgrade_needed": license_type not in ("AMP", "PL", "ML"),
        })

    req = requirements.get(activity, requirements["survey"])

    return json.dumps({
        "required_license": req["min_license"],
        "fee_kes": req["fee_kes"],
        "fee_usd": round(req["fee_kes"] / 130, 2),  # Approximate KES/USD
        "duration": req["duration"],
        "max_area_km2": req["max_area_km2"],
        "additional_requirements": req.get("additional", []),
        "current_license": license_type,
        "upgrade_needed": license_type not in ("PL", "ML"),
    })


@tool
def royalty_calculator(gross_revenue_usd: float, mineral_type: str = "gold") -> str:
    """
    Calculate royalty payable under Kenya Mining Act 2016.

    Args:
        gross_revenue_usd: Total gross revenue from mineral sales
        mineral_type: Type of mineral ("gold", "copper", "gemstone", "industrial")

    Returns:
        JSON string with royalty amount and percentage.
    """
    royalty_rates = {
        "gold": 5.0,
        "silver": 5.0,
        "copper": 5.0,
        "zinc": 5.0,
        "lead": 5.0,
        "gemstone": 10.0,
        "industrial": 2.0,
        "coal": 5.0,
    }

    rate = royalty_rates.get(mineral_type.lower(), 5.0)
    royalty = gross_revenue_usd * (rate / 100)

    return json.dumps({
        "mineral_type": mineral_type,
        "royalty_rate_pct": rate,
        "gross_revenue_usd": gross_revenue_usd,
        "royalty_usd": round(royalty, 2),
        "net_after_royalty_usd": round(gross_revenue_usd - royalty, 2),
        "legal_reference": "Kenya Mining Act 2016, Fifth Schedule",
    })


# ===========================================================================
# Tool registry — used by agents to bind tools to LLM
# ===========================================================================

# All tools organized by agent
SAMPLING_TOOLS = [gps_waypoint_generator, route_optimizer]
ANALYSIS_TOOLS = [xrf_analyzer]
GEOLOGY_TOOLS = [deposit_model_lookup, band_ratio_calculator]
MARKET_TOOLS = [cut_off_calculator, deposit_valuator]
COMPLIANCE_TOOLS = [license_checker, royalty_calculator]
REPORT_TOOLS = []  # Report agent uses pure LLM synthesis

ALL_TOOLS = (
    SAMPLING_TOOLS
    + ANALYSIS_TOOLS
    + GEOLOGY_TOOLS
    + MARKET_TOOLS
    + COMPLIANCE_TOOLS
    + REPORT_TOOLS
)


def get_tools_for_agent(agent_name: str) -> list:
    """Get the tool list for a specific agent."""
    tool_map = {
        "sampling": SAMPLING_TOOLS,
        "analysis": ANALYSIS_TOOLS,
        "geology": GEOLOGY_TOOLS,
        "market": MARKET_TOOLS,
        "report": REPORT_TOOLS,
        "compliance": COMPLIANCE_TOOLS,
    }
    return tool_map.get(agent_name, [])


# ---------------------------------------------------------------------------
# MCP Server (stdio transport)
# ---------------------------------------------------------------------------

def create_mcp_server():
    """
    Create an MCP server exposing all AfriMine tools.

    This uses the langchain MCP adapter. In production, each agent
    would have its own MCP server process for isolation.

    Usage:
        python mcp_servers.py  # Starts stdio MCP server
    """
    try:
        from langchain_mcp_adapters.server import create_mcp_server_from_tools

        server = create_mcp_server_from_tools(
            tools=ALL_TOOLS,
            name="afrimine-tools",
            description="AfriMine AI agent tools for mineral analysis, geology, market data, and compliance",
        )
        return server

    except ImportError:
        logger.warning(
            "langchain-mcp-adapters not installed. "
            "Install with: pip install langchain-mcp-adapters"
        )
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = create_mcp_server()
    if server:
        logger.info("Starting AfriMine MCP server (stdio transport)")
        server.run(transport="stdio")
    else:
        logger.error("Cannot start MCP server — missing dependencies")
