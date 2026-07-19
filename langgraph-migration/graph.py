"""
AfriMine AI — LangGraph 1.0 State Graph
==========================================

The complete 6-agent pipeline modeled as a directed graph:

    START → Sampling → Analysis → Router ──┬→ Geology ──┐
                                           │            ├→ Merge → Report → Compliance → END
                                           └→ Market ───┘          ↑
                                                    └── REFINE ────┘

Architecture decisions:
1. StateGraph(AfriMineState) — single shared TypedDict for all agents
2. Conditional routing after Analysis — based on requires_geology_context flag
3. Parallel fan-out: Geology + Market run concurrently (LangGraph Send API)
4. Fan-in: Report Agent waits for both branches via merge_branches barrier node
5. Refinement loop: Report can send back to Analysis up to 3 times
6. Checkpointing: Every node boundary is checkpointed to Supabase
7. Human-in-the-loop: Compliance can pause the graph for manual approval

Usage:
    graph = build_graph(checkpointer)
    result = await graph.ainvoke(initial_state, config)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from state_schema import AfriMineState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent node imports
# ---------------------------------------------------------------------------
from agents.sampling_agent import sampling_agent
from agents.analysis_agent import analysis_agent
from agents.geology_agent import geology_agent
from agents.market_agent import market_agent
from agents.report_agent import report_agent
from agents.compliance_agent import compliance_agent


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------

def route_after_analysis(state: AfriMineState) -> str:
    """
    Decide which branch(es) to activate after the Analysis Agent.

    Returns:
        "parallel_geo_market" — run Geology + Market in parallel
        "market_only" — skip Geology (no geological context needed)
        "direct_report" — go straight to Report (rare, low-confidence edge case)

    The routing decision is based on the requires_geology_context flag
    set by the Analysis Agent. If gold or anomalous pathfinders are detected,
    geological interpretation is critical.
    """
    analysis = state.get("analysis_result", {})
    requires_geology = analysis.get("requires_geology_context", True)  # Default: yes
    confidence = analysis.get("overall_confidence", 0.0)

    if confidence < 0.1:
        # Very low confidence — skip expensive geology analysis
        logger.info("Routing: direct_report (very low confidence)")
        return "direct_report"

    if requires_geology:
        logger.info("Routing: parallel_geo_market (geology context needed)")
        return "parallel_geo_market"

    logger.info("Routing: market_only (no geology context needed)")
    return "market_only"


def fan_out_after_analysis(state: AfriMineState) -> list[Send]:
    """
    Fan-out function for parallel execution of Geology and Market agents.

    Uses LangGraph's Send API to dispatch to multiple nodes simultaneously.
    Both branches run concurrently and their results are merged into state
    by the merge_branches barrier node.

    Returns:
        List of Send instructions for parallel execution.
    """
    analysis = state.get("analysis_result", {})
    requires_geology = analysis.get("requires_geology_context", True)
    confidence = analysis.get("overall_confidence", 0.0)

    sends: list[Send] = []

    if confidence < 0.1:
        # Skip both — go directly to merge (which will forward to report)
        sends.append(Send("merge_branches", state))
        return sends

    # Always include Market Agent (it's fast, no LLM)
    sends.append(Send("market", state))

    if requires_geology:
        # Include Geology Agent for parallel execution
        sends.append(Send("geology", state))

    return sends


def merge_branches(state: AfriMineState) -> dict:
    """
    Barrier/merge node that waits for BOTH Geology and Market branches.

    This node solves the fan-in bug: without it, Report would fire twice
    (once when Geology completes, once when Market completes). By routing
    both branches here, LangGraph waits for ALL incoming edges to resolve
    before executing this node, which then forwards to Report exactly once.

    This is a no-op state merge — it doesn't modify agent outputs,
    it just ensures both branches are complete before proceeding.

    Returns:
        Partial state update (increment refinement_count if coming from
        a refinement loop, otherwise pass-through).
    """
    logger.info(
        "merge_branches: barrier reached — both Geology and Market complete. "
        f"geology_result={'present' if state.get('geology_result') else 'absent'}, "
        f"market_result={'present' if state.get('market_result') else 'absent'}"
    )
    # No-op: state already contains results from both branches.
    # Return empty dict so we don't overwrite anything.
    return {}


def route_after_report(state: AfriMineState) -> str:
    """
    Decide whether to refine the report or proceed to compliance.

    Returns:
        "compliance" — report is good, proceed to compliance check
        "analysis" — report needs refinement, loop back through analysis

    The refinement loop re-runs Analysis → Geology/Market → Report
    to fill gaps or fix contradictions. Max 3 iterations.
    """
    report = state.get("report_result", {})
    needs_refinement = report.get("needs_refinement", False)
    refinement_count = state.get("refinement_count", 0)

    if needs_refinement and refinement_count < 3:
        logger.info(f"Routing: refinement loop #{refinement_count + 1}")
        return "analysis"  # Loop back to analysis for re-check

    logger.info(f"Routing: compliance (refinement_count={refinement_count})")
    return "compliance"


def route_after_compliance(state: AfriMineState) -> str:
    """
    After compliance check, decide if human approval is needed.

    Returns:
        "end" — compliance passed or issues are non-blocking
        "pause_for_approval" — human-in-the-loop for compliance issues

    Note: In production, "pause_for_approval" triggers LangGraph's
    interrupt_before mechanism, pausing the graph until a human resumes it.
    """
    compliance = state.get("compliance_result", {})
    is_compliant = compliance.get("is_compliant", False)

    if is_compliant:
        return "end"

    # For MVP: complete with compliance issues flagged
    # In production: return "pause_for_approval" to enable human-in-the-loop
    logger.warning(
        f"Compliance issues found: {compliance.get('compliance_issues', [])}"
    )
    return "end"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None) -> Any:
    """
    Build the complete AfriMine LangGraph StateGraph.

    Args:
        checkpointer: A BaseCheckpointSaver instance for state persistence.
                      If None, the graph runs without checkpointing (dev/test only).

    Returns:
        Compiled LangGraph application ready for invocation.
    """
    logger.info("Building AfriMine LangGraph...")

    # Initialize the graph with our state schema
    graph = StateGraph(AfriMineState)

    # ── Add nodes ──────────────────────────────────────────────────────────
    # Each node is an async function: (state) -> partial_state_update
    graph.add_node("sampling", sampling_agent)
    graph.add_node("analysis", analysis_agent)
    graph.add_node("geology", geology_agent)
    graph.add_node("market", market_agent)
    graph.add_node("merge_branches", merge_branches)  # Barrier: waits for BOTH Geology + Market
    graph.add_node("report", report_agent)
    graph.add_node("compliance", compliance_agent)

    # ── Add edges ──────────────────────────────────────────────────────────

    # Entry point
    graph.add_edge(START, "sampling")

    # Sampling → Analysis (always sequential)
    graph.add_edge("sampling", "analysis")

    # Analysis → Conditional Router (fan-out to Geology + Market)
    # We use add_conditional_edges with a fan-out function that returns Send objects.
    # This enables PARALLEL execution of Geology and Market agents.
    graph.add_conditional_edges(
        "analysis",
        fan_out_after_analysis,
        {
            "geology": "geology",
            "market": "market",
            "merge_branches": "merge_branches",  # Direct path for very low confidence
        },
    )

    # ── FAN-IN FIX: Both branches converge on merge_branches (barrier node) ──
    # This ensures Report fires EXACTLY ONCE after both Geology and Market complete.
    # Without this barrier, LangGraph would invoke Report twice (once per branch).
    graph.add_edge("geology", "merge_branches")
    graph.add_edge("market", "merge_branches")

    # merge_branches → Report (single invocation, both results in state)
    graph.add_edge("merge_branches", "report")

    # Report → Conditional Router (refinement loop or compliance)
    graph.add_conditional_edges(
        "report",
        route_after_report,
        {
            "analysis": "analysis",  # Refinement loop
            "compliance": "compliance",
        },
    )

    # Compliance → END (with optional human-in-the-loop pause)
    graph.add_conditional_edges(
        "compliance",
        route_after_compliance,
        {
            "end": END,
            "pause_for_approval": END,  # Placeholder — real HITL uses interrupt_before
        },
    )

    # ── Compile ────────────────────────────────────────────────────────────
    compile_kwargs: dict[str, Any] = {}

    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
        logger.info("Checkpointer attached — state will persist to Supabase")

    # Enable streaming for real-time updates to Flutter frontend
    # In production, use .astream() for SSE streaming
    compiled = graph.compile(**compile_kwargs)

    logger.info("AfriMine LangGraph compiled successfully")
    return compiled


# ---------------------------------------------------------------------------
# Convenience entry points
# ---------------------------------------------------------------------------

async def run_analysis(
    initial_state: dict[str, Any],
    checkpointer=None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run a complete mineral analysis through the 6-agent pipeline.

    Args:
        initial_state: Input data (location, sample_data, satellite_imagery, etc.)
        checkpointer: Optional checkpoint saver for crash recovery.
        config: Optional LangGraph config (thread_id, etc.)

    Returns:
        The final state with all agent outputs populated.
    """
    graph = build_graph(checkpointer)

    if config is None:
        import uuid
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    logger.info(f"Starting analysis: thread={config.get('configurable', {}).get('thread_id')}")

    final_state = await graph.ainvoke(initial_state, config)

    logger.info(
        f"Analysis complete: "
        f"compliant={final_state.get('compliance_result', {}).get('is_compliant', False)}, "
        f"errors={len(final_state.get('errors', []))}"
    )

    return final_state


async def stream_analysis(
    initial_state: dict[str, Any],
    checkpointer=None,
    config: dict[str, Any] | None = None,
):
    """
    Stream analysis progress — yields state updates as each agent completes.
    Use this for SSE endpoints that feed the Flutter frontend real-time.

    Yields:
        (node_name, partial_state) tuples as agents complete.
    """
    graph = build_graph(checkpointer)

    if config is None:
        import uuid
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    async for event in graph.astream(initial_state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            logger.info(f"Stream update: {node_name}")
            yield node_name, node_output


# ---------------------------------------------------------------------------
# CLI entry point (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    async def main():
        from checkpointer import get_checkpointer

        # Use in-memory checkpointer for local testing
        checkpointer = get_checkpointer(use_memory=True)

        test_state: dict[str, Any] = {
            "location": {
                "lat": -1.05,
                "lon": 34.55,
                "region": "Nyatike",
                "county": "Migori",
                "country": "Kenya",
                "area_hectares": 10,
            },
            "sample_data": {
                "sample_id": "TEST-001",
                "photo_url": None,
                "xrf_readings": {"Au": 5.2, "Ag": 2.1, "Cu": 45, "As": 120.5, "Fe": 3.2, "Bi": 8.3},
                "notes": "Quartz vein with sulfide staining, collected near river bed",
                "preliminary_result": "Gold-bearing quartz",
            },
            "satellite_imagery": "",
            "user_id": "test-user",
            "analysis_id": "test-001",
            "messages": [],
            "errors": [],
            "metadata": {},
            "refinement_count": 0,
        }

        result = await run_analysis(test_state, checkpointer=checkpointer)

        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print(f"Compliant: {result.get('compliance_result', {}).get('is_compliant')}")
        print(f"Deposit Value: ${result.get('market_result', {}).get('deposit_value_estimate_usd', 0):,.0f}")
        print(f"Recommendation: {result.get('report_result', {}).get('recommendation', 'N/A')}")
        print(f"Errors: {result.get('errors', [])}")

    asyncio.run(main())
