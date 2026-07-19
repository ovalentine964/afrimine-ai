"""
AfriMine AI — Economics MCP Server
=====================================
Provides economic calculation tools for the Market agent.

Tools:
  - calculate_npv: Net Present Value calculation
  - calculate_dcf: Discounted Cash Flow analysis
  - calculate_irr: Internal Rate of Return
  - sensitivity_analysis: Sensitivity analysis on key variables
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base_mcp import BaseMCPServer, MCPTool

logger = logging.getLogger(__name__)


class EconomicsMCPServer(BaseMCPServer):
    name = "economics-mcp"
    version = "1.0.0"

    def _register_tools(self):
        self.register_tool(MCPTool(
            name="calculate_npv",
            description="Calculate Net Present Value of a mining project",
            parameters={
                "type": "object",
                "properties": {
                    "cash_flows": {"type": "array", "items": {"type": "number"}, "description": "Annual cash flows (USD)"},
                    "discount_rate": {"type": "number", "description": "Discount rate (e.g., 0.10 for 10%)", "default": 0.10},
                    "initial_investment": {"type": "number", "description": "Initial capital expenditure (USD)"},
                },
                "required": ["cash_flows", "initial_investment"],
            },
            handler=self._calculate_npv,
            required_permissions=["market", "report"],
        ))

        self.register_tool(MCPTool(
            name="calculate_irr",
            description="Calculate Internal Rate of Return for a mining project",
            parameters={
                "type": "object",
                "properties": {
                    "cash_flows": {"type": "array", "items": {"type": "number"}},
                    "initial_investment": {"type": "number"},
                },
                "required": ["cash_flows", "initial_investment"],
            },
            handler=self._calculate_irr,
            required_permissions=["market", "report"],
        ))

        self.register_tool(MCPTool(
            name="sensitivity_analysis",
            description="Run sensitivity analysis on key variables (price, grade, recovery, cost)",
            parameters={
                "type": "object",
                "properties": {
                    "base_case": {"type": "object", "description": "Base case parameters"},
                    "variables": {"type": "array", "items": {"type": "string"}, "description": "Variables to vary"},
                    "range_percent": {"type": "number", "default": 20, "description": "Variation range (%)"},
                },
                "required": ["base_case"],
            },
            handler=self._sensitivity_analysis,
            required_permissions=["market", "report"],
        ))

    async def _calculate_npv(self, cash_flows: List[float], initial_investment: float,
                              discount_rate: float = 0.10) -> Dict[str, Any]:
        logger.info(f"Calculating NPV: investment=${initial_investment}, rate={discount_rate}")
        # NPV = -InitialInvestment + sum(CF_t / (1+r)^t)
        try:
            npv = -initial_investment
            for t, cf in enumerate(cash_flows, 1):
                npv += cf / (1 + discount_rate) ** t
            return {
                "npv_usd": round(npv, 2),
                "initial_investment": initial_investment,
                "discount_rate": discount_rate,
                "cash_flows": cash_flows,
                "is_positive": npv > 0,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _calculate_irr(self, cash_flows: List[float],
                              initial_investment: float) -> Dict[str, Any]:
        logger.info(f"Calculating IRR: investment=${initial_investment}")
        # PLACEHOLDER: Use numpy.irr or bisection method
        return {
            "status": "placeholder",
            "message": "IRR calculation pending numpy integration",
            "irr": None,
        }

    async def _sensitivity_analysis(self, base_case: dict, variables: List[str] = None,
                                     range_percent: float = 20) -> Dict[str, Any]:
        logger.info(f"Running sensitivity analysis on {variables}")
        return {
            "status": "placeholder",
            "message": "Sensitivity analysis pending",
            "results": {},
        }

    async def health_check(self) -> bool:
        return True
