"""
AfriMine AI — Market Agent
Tracks mineral commodity prices, calculates economic viability.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# Approximate mineral prices (USD) — would be live-fetched in production
MINERAL_PRICES_USD = {
    "gold": {"unit": "g", "price": 75.0, "currency": "USD"},       # ~$2,330/troy oz
    "copper": {"unit": "lb", "price": 4.20, "currency": "USD"},
    "titanium": {"unit": "t", "price": 6500.0, "currency": "USD"},  # ilmenite concentrate
    "graphite": {"unit": "t", "price": 800.0, "currency": "USD"},   # flake graphite
    "fluorite": {"unit": "t", "price": 350.0, "currency": "USD"},   # acid grade
    "manganese": {"unit": "t", "price": 4.50, "currency": "USD"},   # per Mn content unit
    "bauxite": {"unit": "t", "price": 55.0, "currency": "USD"},
    "limestone": {"unit": "t", "price": 15.0, "currency": "USD"},
    "soda_ash": {"unit": "t", "price": 250.0, "currency": "USD"},
    "diatomite": {"unit": "t", "price": 200.0, "currency": "USD"},
    "ruby": {"unit": "ct", "price": 1500.0, "currency": "USD"},     # high quality
    "sapphire": {"unit": "ct", "price": 800.0, "currency": "USD"},  # blue, high quality
    "garnet": {"unit": "ct", "price": 15.0, "currency": "USD"},
    "tourmaline": {"unit": "ct", "price": 50.0, "currency": "USD"},
    "sodalite": {"unit": "t", "price": 50.0, "currency": "USD"},
    "vermiculite": {"unit": "t", "price": 120.0, "currency": "USD"},
    "niobium": {"unit": "kg", "price": 45.0, "currency": "USD"},
    "thorium": {"unit": "kg", "price": 30.0, "currency": "USD"},
    "pyrite": {"unit": "t", "price": 10.0, "currency": "USD"},
    "quartz": {"unit": "t", "price": 50.0, "currency": "USD"},
}

# KES exchange rate (approximate)
USD_TO_KES = 155.0


class MarketAgent:
    """
    Agent that tracks mineral commodity prices and evaluates economic viability.
    """

    def __init__(self, gemini_model=None):
        self.name = "Market Agent"
        self.role = "Commodity Market Analyst"
        self.gemini = gemini_model
        self.prices = MINERAL_PRICES_USD.copy()

    def get_price(self, mineral: str) -> dict:
        """Get current price for a mineral."""
        price_data = self.prices.get(mineral.lower())
        if not price_data:
            return {"mineral": mineral, "error": "Price data not available"}

        kes_price = price_data["price"] * USD_TO_KES
        return {
            "mineral": mineral,
            "price_usd": price_data["price"],
            "price_kes": round(kes_price, 2),
            "unit": price_data["unit"],
            "currency": price_data["currency"],
            "timestamp": datetime.now().isoformat(),
        }

    def calculate_economic_viability(
        self,
        mineral: str,
        grade: float,
        grade_unit: str,
        tonnage_estimate: float,
        extraction_cost_per_t: float = 50.0,
    ) -> dict:
        """
        Calculate economic viability of a mineral deposit.

        Args:
            mineral: Mineral name
            grade: Estimated grade
            grade_unit: Unit of grade (% g/t, ppm, ct/t, etc.)
            tonnage_estimate: Estimated total tonnage
            extraction_cost_per_t: Cost per tonne to extract (USD)
        """
        price_data = self.get_price(mineral)
        if "error" in price_data:
            return price_data

        price_per_unit = price_data["price_usd"]
        unit = price_data["unit"]

        # Calculate revenue per tonne of ore
        if grade_unit == "g/t" and unit == "g":
            revenue_per_t = grade * price_per_unit
        elif grade_unit == "%" and unit == "t":
            revenue_per_t = (grade / 100.0) * price_per_unit
        elif grade_unit == "ppm" and unit == "kg":
            revenue_per_t = (grade / 1000.0) * price_per_unit
        elif grade_unit == "ct/t" and unit == "ct":
            revenue_per_t = grade * price_per_unit
        elif grade_unit == "%" and unit == "lb":
            revenue_per_t = (grade / 100.0) * tonnage_estimate * price_per_unit * 2204.62 / tonnage_estimate
        else:
            revenue_per_t = grade * price_per_unit * 0.01  # rough estimate

        profit_per_t = revenue_per_t - extraction_cost_per_t
        total_revenue = revenue_per_t * tonnage_estimate
        total_cost = extraction_cost_per_t * tonnage_estimate
        total_profit = profit_per_t * tonnage_estimate

        viability = "economically_viable" if profit_per_t > 0 else "not_viable"
        if profit_per_t > 0 and profit_per_t < extraction_cost_per_t * 0.2:
            viability = "marginal"

        return {
            "mineral": mineral,
            "grade": grade,
            "grade_unit": grade_unit,
            "tonnage_estimate": tonnage_estimate,
            "price_per_unit_usd": price_per_unit,
            "revenue_per_tonne_usd": round(revenue_per_t, 2),
            "cost_per_tonne_usd": extraction_cost_per_t,
            "profit_per_tonne_usd": round(profit_per_t, 2),
            "total_revenue_usd": round(total_revenue, 2),
            "total_cost_usd": round(total_cost, 2),
            "total_profit_usd": round(total_profit, 2),
            "total_profit_kes": round(total_profit * USD_TO_KES, 2),
            "profit_margin_pct": round((profit_per_t / max(revenue_per_t, 0.01)) * 100, 1),
            "viability": viability,
            "break_even_grade": round(extraction_cost_per_t / max(price_per_unit, 0.01), 4),
        }

    def get_market_summary(self, minerals: list[str]) -> dict:
        """Get market summary for multiple minerals."""
        summary = {}
        for mineral in minerals:
            summary[mineral] = self.get_price(mineral)
        return {
            "minerals": summary,
            "exchange_rate": {"USD_KES": USD_TO_KES},
            "timestamp": datetime.now().isoformat(),
        }

    def compare_alternatives(self, mineral: str, grade: float, tonnage: float) -> list[dict]:
        """Compare economic returns across minerals for the same deposit parameters."""
        results = []
        for m_name in self.prices:
            result = self.calculate_economic_viability(m_name, grade, "g/t", tonnage)
            if "error" not in result:
                results.append(result)
        results.sort(key=lambda r: -r.get("profit_per_tonne_usd", 0))
        return results

    def generate_market_report(self, analysis_results: list[dict]) -> str:
        """Generate a market analysis report from sample analysis results."""
        minerals = list(set(
            r.get("classification", {}).get("mineral", "unknown")
            for r in analysis_results if "error" not in r
        ))

        report = [
            "# AfriMine AI — Market Analysis Report",
            "",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            f"Exchange Rate: 1 USD = {USD_TO_KES} KES",
            "",
            "## Commodity Prices",
        ]

        for mineral in minerals:
            price = self.get_price(mineral)
            if "error" not in price:
                report.append(
                    f"- **{mineral.title()}**: ${price['price_usd']}/{price['unit']} "
                    f"(KES {price['price_kes']}/{price['unit']})"
                )

        report.append("\n## Economic Viability Assessment")
        for r in analysis_results:
            if "error" in r:
                continue
            mineral = r.get("classification", {}).get("mineral", "unknown")
            grade = r.get("grade_estimation", {}).get("grade", 0)
            unit = r.get("grade_estimation", {}).get("unit", "%")
            viability = self.calculate_economic_viability(mineral, grade, unit, 1000)
            report.append(
                f"- **{mineral}** ({grade} {unit}): {viability['viability']} "
                f"(profit ${viability['profit_per_tonne_usd']}/t)"
            )

        return "\n".join(report)
