"""
AfriMine AI — Agent Nodes for LangGraph
========================================

Each module exports a single async function that takes AfriMineState
and returns a partial state dict with the agent's output.

    async def sampling_agent(state: AfriMineState) -> dict:
        ...
        return {"sampling_result": {...}, "current_step": "analysis"}

LangGraph calls these as graph nodes. The returned dict is merged
into the shared state.
"""

from agents.sampling_agent import sampling_agent
from agents.analysis_agent import analysis_agent
from agents.geology_agent import geology_agent
from agents.market_agent import market_agent
from agents.report_agent import report_agent
from agents.compliance_agent import compliance_agent

__all__ = [
    "sampling_agent",
    "analysis_agent",
    "geology_agent",
    "market_agent",
    "report_agent",
    "compliance_agent",
]
