"""
AfriMine AI — Market Agent
============================

Role: Fetch real-time gold/copper prices, calculate deposit value,
      and assess economic viability using cut-off grade analysis.

When it runs: In parallel with Geology Agent, after Analysis Agent (conditional).
What it reads: analysis_result, location.
What it writes: market_result.

Architecture notes:
- This agent uses NO LLM — pure Python calculations
- Price data from yfinance (gold/copper futures) or fallback APIs
- Cut-off grade = (operating_cost / (metal_price × recovery_rate))
- Deposit value uses simple NPV with 10% discount rate
- Runs in PARALLEL with Geology Agent (LangGraph fan-out)
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

logger = logging.getLogger(__name__)
slog = structlog.get_logger(__name__)

# --- Constants (Kenya-specific) ---
KENYA_ROYALTY_RATE_PCT = 5.0  # Kenya Mining Act 2016: 5% royalty
DEFAULT_RECOVERY_RATE = 0.85  # Gravity + cyanide leaching
DISCOUNT_RATE = 0.10  # 10% for early-stage projects
GOLD_OZ_TO_GRAMS = 31.1035
COPPER_LB_TO_KG = 0.453592


async def _fetch_gold_price_usd_oz() -> float:
    """Fetch current gold price in USD/oz. Falls back to cached value."""
    try:
        import yfinance as yf
        ticker = yf.Ticker("GC=F")  # Gold futures
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            slog.info("gold_price_fetched", price=price, source="yfinance")
            return price
    except Exception as e:
        slog.warning("gold_price_fetch_failed", error=str(e))

    # Fallback: approximate gold price (update periodically)
    slog.warning("using_fallback_gold_price", price=2350.0)
    return 2350.0


async def _fetch_copper_price_usd_lb() -> float:
    """Fetch current copper price in USD/lb."""
    try:
        import yfinance as yf
        ticker = yf.Ticker("HG=F")  # Copper futures
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            slog.info("copper_price_fetched", price=price, source="yfinance")
            return price
    except Exception as e:
        slog.warning("copper_price_fetch_failed", error=str(e))

    slog.warning("using_fallback_copper_price", price=4.20)
    return 4.20


def _calculate_cut_off_grade(
    operating_cost_usd_per_tonne: float,
    metal_price_usd_per_gram: float,
    recovery_rate: float,
) -> float:
    """
    Calculate cut-off grade in g/t.

    Cut-off grade = operating_cost / (metal_price_per_gram × recovery_rate)
    Below this grade, mining is not profitable.
    """
    denominator = metal_price_usd_per_gram * recovery_rate
    if denominator <= 0:
        return 0.0
    return operating_cost_usd_per_tonne / denominator


def _calculate_deposit_value(
    grade_gpt: float,
    tonnage: float,
    gold_price_usd_oz: float,
    recovery_rate: float,
    discount_rate: float,
    mine_life_years: int = 5,
) -> float:
    """
    Estimate deposit value using simplified DCF.

    Args:
        grade_gpt: Average grade in grams per tonne
        tonnage: Estimated tonnes of ore
        gold_price_usd_oz: Current gold price
        recovery_rate: Metallurgical recovery (0.0-1.0)
        discount_rate: Discount rate for NPV
        mine_life_years: Assumed mine life

    Returns:
        NPV in USD (rough estimate)
    """
    gold_price_per_gram = gold_price_usd_oz / GOLD_OZ_TO_GRAMS
    contained_gold_grams = grade_gpt * tonnage
    recoverable_gold_grams = contained_gold_grams * recovery_rate
    gross_value = recoverable_gold_grams * gold_price_per_gram

    # Simple NPV: spread evenly over mine life
    annual_value = gross_value / mine_life_years
    npv = sum(annual_value / (1 + discount_rate) ** year for year in range(1, mine_life_years + 1))

    return round(npv, 2)


def _estimate_tonnage(sample_data: dict[str, Any], location: dict[str, Any]) -> float:
    """
    Rough tonnage estimate based on area and assumed depth.
    For artisanal sites: typically 10,000–100,000 tonnes.
    """
    area_hectares = location.get("area_hectares", 10)
    depth_m = 10  # Assume 10m depth for surface prospecting
    density_tonnes_per_m3 = 2.7  # Average rock density

    volume_m3 = area_hectares * 10_000 * depth_m  # 1 hectare = 10,000 m²
    return volume_m3 * density_tonnes_per_m3


def _assess_trend(gold_price: float) -> str:
    """Simple trend assessment (production version would use 30-day moving average)."""
    if gold_price > 2400:
        return "bullish"
    elif gold_price < 2200:
        return "bearish"
    return "stable"


async def market_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Market Agent node function.

    Fetches commodity prices and calculates deposit economic value.
    No LLM required — pure data fetching and calculation.

    Args:
        state: The current AfriMineState.

    Returns:
        Partial state update with market_result.
    """
    analysis_id = state.get("analysis_id", "unknown")
    slog.info("market_agent_starting", analysis_id=analysis_id, branch="parallel")

    try:
        # Fetch prices in parallel
        import asyncio
        gold_price, copper_price = await asyncio.gather(
            _fetch_gold_price_usd_oz(),
            _fetch_copper_price_usd_lb(),
        )

        analysis = state.get("analysis_result", {})
        location = state.get("location", {})
        minerals = analysis.get("minerals", [])

        # Find gold grade from analysis
        gold_grade_gpt = 0.0
        for mineral in minerals:
            if "gold" in mineral.get("mineral_name", "").lower():
                gold_grade_gpt = mineral.get("grade_estimate_gpt", 0.0)
                break

        # If no gold grade from vision, try XRF
        if gold_grade_gpt == 0.0:
            xrf = analysis.get("xrf_data", {})
            gold_grade_gpt = xrf.get("Au", 0.0)  # Already in gpt from XRF

        # Calculate economic metrics
        gold_price_per_gram = gold_price / GOLD_OZ_TO_GRAMS
        tonnage = _estimate_tonnage(state.get("sample_data", {}), location)
        cut_off_grade = _calculate_cut_off_grade(
            operating_cost_usd_per_tonne=30.0,  # Typical ASM operating cost
            metal_price_usd_per_gram=gold_price_per_gram,
            recovery_rate=DEFAULT_RECOVERY_RATE,
        )

        # Deposit value estimate
        deposit_value = 0.0
        if gold_grade_gpt > cut_off_grade:
            deposit_value = _calculate_deposit_value(
                grade_gpt=gold_grade_gpt,
                tonnage=tonnage,
                gold_price_usd_oz=gold_price,
                recovery_rate=DEFAULT_RECOVERY_RATE,
                discount_rate=DISCOUNT_RATE,
            )

        # Market risk factors
        risk_factors = []
        if gold_grade_gpt < cut_off_grade:
            risk_factors.append(f"Grade ({gold_grade_gpt:.2f} g/t) below cut-off ({cut_off_grade:.2f} g/t)")
        if gold_grade_gpt > 0 and gold_grade_gpt < 1.0:
            risk_factors.append("Low-grade deposit — bulk mining required for viability")
        if gold_price < 2000:
            risk_factors.append("Gold price below $2,000/oz — depressed market")

        result = {
            "gold_price_usd_oz": round(gold_price, 2),
            "copper_price_usd_lb": round(copper_price, 2),
            "commodity_trend": _assess_trend(gold_price),
            "deposit_value_estimate_usd": deposit_value,
            "cut_off_grade_gpt": round(cut_off_grade, 2),
            "recovery_rate_assumption": DEFAULT_RECOVERY_RATE,
            "royalty_rate_pct": KENYA_ROYALTY_RATE_PCT,
            "market_risk_factors": risk_factors,
            "valuation_notes": (
                f"Gold at ${gold_price:,.0f}/oz. "
                f"Cut-off grade: {cut_off_grade:.2f} g/t. "
                f"Estimated deposit value: ${deposit_value:,.0f} NPV "
                f"(assuming {tonnage:,.0f}t at {gold_grade_gpt:.2f} g/t, "
                f"{DEFAULT_RECOVERY_RATE:.0%} recovery, {DISCOUNT_RATE:.0%} discount rate)."
            ),
        }

        slog.info(
            "market_agent_complete",
            analysis_id=analysis_id,
            gold_price=gold_price,
            deposit_value=deposit_value,
            cut_off=cut_off_grade,
        )

        return {
            "market_result": result,
            "current_step": "report_fan_in",
            "messages": [
                HumanMessage(
                    content=f"Market: Gold ${gold_price:,.0f}/oz, "
                            f"deposit value ${deposit_value:,.0f} NPV, "
                            f"cut-off {cut_off_grade:.2f} g/t.",
                    name="market_agent",
                )
            ],
        }

    except Exception as e:
        error_msg = f"Market Agent error: {type(e).__name__}: {e}"
        slog.error("market_agent_error", error=error_msg)
        return {
            "market_result": {
                "gold_price_usd_oz": 0.0,
                "deposit_value_estimate_usd": 0.0,
                "market_risk_factors": [error_msg],
            },
            "current_step": "report_fan_in",
            "errors": [error_msg],
        }
