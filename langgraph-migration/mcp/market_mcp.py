"""
AfriMine AI — Market MCP Server
=================================
Provides commodity price fetching and economic calculation tools for the Market agent.

Tools:
  - get_metal_price: Fetch current spot price for a metal
  - get_price_history: Get historical price data
  - calculate_deposit_value: Estimate deposit value from grade + tonnage
  - calculate_royalty: Calculate Kenya Mining Act royalty
  - calculate_cutoff_grade: Determine economic cut-off grade

Data sources: metals.live API, Kitco, LME (cached in Supabase)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_mcp import BaseMCPServer, MCPTool

logger = logging.getLogger(__name__)


class MarketMCPServer(BaseMCPServer):
    name = "market-mcp"
    version = "1.0.0"

    def __init__(self, supabase_client=None):
        self.db = supabase_client
        super().__init__()

    def _register_tools(self):
        self.register_tool(MCPTool(
            name="get_metal_price",
            description="Fetch current spot price for a metal (gold, silver, copper, etc.) from metals.live or cached data",
            parameters={
                "type": "object",
                "properties": {
                    "metal": {
                        "type": "string",
                        "enum": ["gold", "silver", "copper", "zinc", "lead", "nickel",
                                 "platinum", "palladium", "cobalt", "tungsten", "tantalum"],
                        "description": "Metal name",
                    },
                    "currency": {
                        "type": "string",
                        "enum": ["USD", "KES"],
                        "description": "Price currency",
                        "default": "USD",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["oz", "tonne", "kg", "lb"],
                        "description": "Price unit",
                        "default": "oz",
                    },
                },
                "required": ["metal"],
            },
            handler=self._get_metal_price,
            required_permissions=["market", "report"],
        ))

        self.register_tool(MCPTool(
            name="get_price_history",
            description="Get historical price data for a metal over a time period",
            parameters={
                "type": "object",
                "properties": {
                    "metal": {"type": "string", "description": "Metal name"},
                    "period": {
                        "type": "string",
                        "enum": ["7d", "30d", "90d", "1y", "5y"],
                        "description": "Time period",
                        "default": "1y",
                    },
                },
                "required": ["metal"],
            },
            handler=self._get_price_history,
            required_permissions=["market", "report"],
        ))

        self.register_tool(MCPTool(
            name="calculate_deposit_value",
            description="Estimate total deposit value from mineral grade, tonnage, and current prices",
            parameters={
                "type": "object",
                "properties": {
                    "mineral": {"type": "string", "description": "Primary mineral"},
                    "grade_ppm": {"type": "number", "description": "Mineral grade in ppm (or g/t for gold)"},
                    "grade_unit": {
                        "type": "string",
                        "enum": ["ppm", "g/t", "%", "oz/t"],
                        "description": "Grade unit",
                        "default": "ppm",
                    },
                    "tonnage": {"type": "number", "description": "Estimated ore tonnage"},
                    "recovery_rate": {
                        "type": "number",
                        "description": "Metallurgical recovery rate (0-1)",
                        "default": 0.85,
                    },
                },
                "required": ["mineral", "grade_ppm", "tonnage"],
            },
            handler=self._calculate_deposit_value,
            required_permissions=["market", "report"],
        ))

        self.register_tool(MCPTool(
            name="calculate_royalty",
            description="Calculate royalty payable under Kenya Mining Act 2016 Section 103",
            parameters={
                "type": "object",
                "properties": {
                    "mineral": {"type": "string", "description": "Mineral type"},
                    "gross_value_usd": {"type": "number", "description": "Gross value in USD"},
                    "license_type": {
                        "type": "string",
                        "enum": ["artisanal", "small_scale", "large_scale", "exploration"],
                        "description": "Mining license type",
                        "default": "small_scale",
                    },
                },
                "required": ["mineral", "gross_value_usd"],
            },
            handler=self._calculate_royalty,
            required_permissions=["market", "compliance", "report"],
        ))

        self.register_tool(MCPTool(
            name="calculate_cutoff_grade",
            description="Determine economic cut-off grade: the minimum grade at which mining is profitable",
            parameters={
                "type": "object",
                "properties": {
                    "mineral": {"type": "string", "description": "Mineral type"},
                    "mining_cost_per_tonne": {
                        "type": "number",
                        "description": "Total mining + processing cost per tonne (USD)",
                        "default": 30,
                    },
                    "recovery_rate": {
                        "type": "number",
                        "description": "Metallurgical recovery (0-1)",
                        "default": 0.85,
                    },
                },
                "required": ["mineral"],
            },
            handler=self._calculate_cutoff_grade,
            required_permissions=["market", "geology"],
        ))

    async def _get_metal_price(self, metal: str, currency: str = "USD",
                                unit: str = "oz") -> Dict[str, Any]:
        """Fetch current metal spot price."""
        logger.info(f"Fetching price: {metal} ({currency}/{unit})")
        # PLACEHOLDER: In production, calls metals.live API or reads from Supabase cache
        # GET https://api.metals.live/v1/spot/{metal}
        return {
            "status": "placeholder",
            "message": "Metal price API integration pending",
            "metal": metal,
            "price": None,
            "currency": currency,
            "unit": unit,
            "source": "metals.live",
            "cached": False,
        }

    async def _get_price_history(self, metal: str, period: str = "1y") -> Dict[str, Any]:
        """Get historical price data."""
        logger.info(f"Fetching price history: {metal} ({period})")
        # PLACEHOLDER: SELECT * FROM agent_long_term_memory WHERE namespace='price:{metal}' ORDER BY timestamp
        return {
            "status": "placeholder",
            "message": "Price history lookup pending",
            "metal": metal,
            "period": period,
            "prices": [],
        }

    async def _calculate_deposit_value(self, mineral: str, grade_ppm: float,
                                        tonnage: float, grade_unit: str = "ppm",
                                        recovery_rate: float = 0.85) -> Dict[str, Any]:
        """Calculate deposit value."""
        logger.info(f"Calculating value: {mineral} at {grade_ppm} {grade_unit}, {tonnage}t")
        # PLACEHOLDER: Formula: value = grade * tonnage * recovery * price_per_unit
        return {
            "status": "placeholder",
            "message": "Deposit value calculation pending price data",
            "mineral": mineral,
            "grade": {"value": grade_ppm, "unit": grade_unit},
            "tonnage": tonnage,
            "recovery_rate": recovery_rate,
            "deposit_value_estimate_usd": None,
            "cutoff_grade": None,
            "is_economic": None,
        }

    async def _calculate_royalty(self, mineral: str, gross_value_usd: float,
                                  license_type: str = "small_scale") -> Dict[str, Any]:
        """Calculate Kenya Mining Act royalty."""
        logger.info(f"Calculating royalty: {mineral}, ${gross_value_usd}, {license_type}")
        # Kenya Mining Act 2016 Section 103: royalty rates vary by mineral and license type
        # Typical rates: 1-5% of gross value
        return {
            "status": "placeholder",
            "message": "Royalty calculation pending",
            "mineral": mineral,
            "gross_value_usd": gross_value_usd,
            "license_type": license_type,
            "royalty_rate_percent": None,
            "royalty_usd": None,
            "kenya_mining_act_section": "section_103",
        }

    async def _calculate_cutoff_grade(self, mineral: str,
                                       mining_cost_per_tonne: float = 30,
                                       recovery_rate: float = 0.85) -> Dict[str, Any]:
        """Calculate economic cut-off grade."""
        logger.info(f"Calculating cut-off grade: {mineral}, cost=${mining_cost_per_tonne}/t")
        # Formula: cutoff = mining_cost / (price_per_unit * recovery)
        return {
            "status": "placeholder",
            "message": "Cut-off grade calculation pending price data",
            "mineral": mineral,
            "mining_cost_per_tonne": mining_cost_per_tonne,
            "recovery_rate": recovery_rate,
            "cutoff_grade_ppm": None,
        }

    async def health_check(self) -> bool:
        """Check API availability."""
        # PLACEHOLDER: Try fetching gold price as health check
        return True
