"""
AfriMine AI — Market Agent (Production)
=========================================

Fetches real-time gold/copper prices, calculates deposit value,
and assesses economic viability using cut-off grade analysis.

Node position: Analysis → MARKET (parallel with Geology) → merge_branches
LLM: None — pure Python calculations
Tools: market-mcp, economics-mcp
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.base import retry_with_backoff
from config import settings
from security.middleware import rate_limiter

logger = logging.getLogger("afrimine.market")

# ── Constants (Kenya-specific) ────────────────────────────────────────────
KENYA_ROYALTY_RATE_PCT = 5.0
DEFAULT_RECOVERY_RATE = 0.85
DISCOUNT_RATE = 0.10
GOLD_OZ_TO_GRAMS = 31.1035
COPPER_LB_TO_KG = 0.453592


async def _fetch_gold_price() -> float:
    """Fetch current gold price in USD/oz with multiple fallbacks."""

    # Source 1: metals.live (free, no auth, lightweight)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.metals.live/v1/spot/gold")
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    price = float(data[0].get("price", 0))
                    if price > 0:
                        # metals.live returns price per oz
                        logger.info(f"Gold price fetched: ${price:,.2f}/oz (metals.live)")
                        return price
    except Exception as e:
        logger.debug(f"metals.live gold fetch failed: {e}")

    # Source 2: yfinance (requires pandas)
    try:
        import yfinance as yf
        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            logger.info(f"Gold price fetched: ${price:,.2f}/oz (yfinance)")
            return price
    except ImportError:
        logger.debug("yfinance not available (pandas not installed)")
    except Exception as e:
        logger.debug(f"yfinance gold fetch failed: {e}")

    # Source 3: Hardcoded fallback
    logger.warning("All gold price sources failed — using fallback price $2,350/oz")
    return 2350.0


async def _fetch_copper_price() -> float:
    """Fetch current copper price in USD/lb with multiple fallbacks."""

    # Source 1: metals.live
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.metals.live/v1/spot/copper")
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) > 0:
                    price_per_kg = float(data[0].get("price", 0))
                    if price_per_kg > 0:
                        # Convert from USD/kg to USD/lb
                        price_per_lb = price_per_kg * 0.453592
                        logger.info(f"Copper price fetched: ${price_per_lb:,.2f}/lb (metals.live)")
                        return price_per_lb
    except Exception as e:
        logger.debug(f"metals.live copper fetch failed: {e}")

    # Source 2: yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker("HG=F")
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            logger.info(f"Copper price fetched: ${price:,.2f}/lb (yfinance)")
            return price
    except ImportError:
        logger.debug("yfinance not available (pandas not installed)")
    except Exception as e:
        logger.debug(f"yfinance copper fetch failed: {e}")

    # Source 3: Hardcoded fallback
    logger.warning("All copper price sources failed — using fallback price $4.20/lb")
    return 4.20


def _calculate_cut_off_grade(
    operating_cost_usd_per_tonne: float,
    metal_price_usd_per_gram: float,
    recovery_rate: float,
) -> float:
    """Calculate cut-off grade in g/t."""
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
    """Estimate deposit value using simplified DCF."""
    gold_price_per_gram = gold_price_usd_oz / GOLD_OZ_TO_GRAMS
    contained_gold_grams = grade_gpt * tonnage
    recoverable_gold_grams = contained_gold_grams * recovery_rate
    gross_value = recoverable_gold_grams * gold_price_per_gram

    annual_value = gross_value / mine_life_years
    npv = sum(
        annual_value / (1 + discount_rate) ** year
        for year in range(1, mine_life_years + 1)
    )
    return round(npv, 2)


def _estimate_tonnage(location: dict[str, Any]) -> float:
    """Rough tonnage estimate based on area and assumed depth."""
    area_hectares = location.get("area_hectares", 10)
    depth_m = 10
    density = 2.7  # Average rock density t/m³
    volume_m3 = area_hectares * 10_000 * depth_m
    return volume_m3 * density


def _assess_trend(gold_price: float) -> str:
    """Simple trend assessment."""
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
    Runs in PARALLEL with Geology Agent.
    """
    analysis_id = state.get("analysis_id", "unknown")
    logger.info(f"[{analysis_id}] Market Agent starting (parallel branch)")

    if not rate_limiter.check("market"):
        return {
            "market_result": {
                "gold_price_usd_oz": 0.0,
                "deposit_value_estimate_usd": 0.0,
                "market_risk_factors": ["Rate limited"],
            },
            "current_step": "merge",
            "errors": ["Market Agent rate limited"],
        }

    rate_limiter.record("market")

    try:
        # Fetch prices in parallel
        gold_price, copper_price = await asyncio.gather(
            retry_with_backoff(_fetch_gold_price),
            retry_with_backoff(_fetch_copper_price),
        )

        analysis = state.get("analysis_result", {})
        location = state.get("location", {})
        minerals = analysis.get("minerals", [])

        # Find gold grade
        gold_grade_gpt = 0.0
        for mineral in minerals:
            if "gold" in mineral.get("mineral_name", "").lower():
                gold_grade_gpt = mineral.get("grade_estimate_gpt", 0.0)
                break

        if gold_grade_gpt == 0.0:
            xrf = analysis.get("xrf_data", {})
            gold_grade_gpt = xrf.get("Au", 0.0)

        # Economic calculations
        gold_price_per_gram = gold_price / GOLD_OZ_TO_GRAMS
        tonnage = _estimate_tonnage(location)
        cut_off_grade = _calculate_cut_off_grade(
            operating_cost_usd_per_tonne=30.0,
            metal_price_usd_per_gram=gold_price_per_gram,
            recovery_rate=DEFAULT_RECOVERY_RATE,
        )

        deposit_value = 0.0
        if gold_grade_gpt > cut_off_grade:
            deposit_value = _calculate_deposit_value(
                grade_gpt=gold_grade_gpt,
                tonnage=tonnage,
                gold_price_usd_oz=gold_price,
                recovery_rate=DEFAULT_RECOVERY_RATE,
                discount_rate=DISCOUNT_RATE,
            )

        # Risk factors
        risk_factors = []
        if gold_grade_gpt < cut_off_grade:
            risk_factors.append(
                f"Grade ({gold_grade_gpt:.2f} g/t) below cut-off ({cut_off_grade:.2f} g/t)"
            )
        if 0 < gold_grade_gpt < 1.0:
            risk_factors.append("Low-grade deposit — bulk mining required")
        if gold_price < 2000:
            risk_factors.append("Gold price below $2,000/oz")

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
                f"Cut-off: {cut_off_grade:.2f} g/t. "
                f"Deposit value: ${deposit_value:,.0f} NPV "
                f"({tonnage:,.0f}t at {gold_grade_gpt:.2f} g/t, "
                f"{DEFAULT_RECOVERY_RATE:.0%} recovery, {DISCOUNT_RATE:.0%} discount)."
            ),
        }

        logger.info(
            f"[{analysis_id}] Market complete: "
            f"gold=${gold_price:,.0f}/oz, value=${deposit_value:,.0f}, "
            f"cut-off={cut_off_grade:.2f} g/t"
        )

        return {
            "market_result": result,
            "current_step": "merge",
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Market: Gold ${gold_price:,.0f}/oz, "
                        f"deposit value ${deposit_value:,.0f} NPV, "
                        f"cut-off {cut_off_grade:.2f} g/t."
                    ),
                }
            ],
        }

    except Exception as e:
        error_msg = f"Market Agent error: {type(e).__name__}: {e}"
        logger.error(f"[{analysis_id}] {error_msg}", exc_info=True)
        return {
            "market_result": {
                "gold_price_usd_oz": 0.0,
                "deposit_value_estimate_usd": 0.0,
                "market_risk_factors": [error_msg],
            },
            "current_step": "merge",
            "errors": [error_msg],
        }
