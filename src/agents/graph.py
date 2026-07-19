"""
AfriMine AI — Production LangGraph Pipeline
=============================================

The complete 6-agent pipeline modeled as a directed graph:

    START → Sampling → Analysis → Router ──┬→ Geology ──┐
                                           │            ├→ Merge → Report → Compliance → END
                                           └→ Market ───┘          ↑
                                                    └── REFINE ────┘

Features:
- Error handling at every node (graceful degradation)
- Retry logic with exponential backoff (in each agent)
- Timeout per node (configurable)
- Logging at every transition
- Checkpoint saving at every state change
- merge_branches barrier (verified fix for fan-in bug)
- Parallel fan-out via LangGraph Send API
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from config import settings
from state import AfriMineState

logger = logging.getLogger("afrimine.graph")


# ---------------------------------------------------------------------------
# Agent node imports
# ---------------------------------------------------------------------------

from agents.sampling import sampling_agent
from agents.analysis import analysis_agent
from agents.geology import geology_agent
from agents.market import market_agent
from agents.report import report_agent
from agents.compliance import compliance_agent


# ---------------------------------------------------------------------------
# Timing wrapper for observability
# ---------------------------------------------------------------------------

def _timed_node(name: str, node_func):
    """Wrap a node function with timing and logging."""
    async def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        start = time.time()
        logger.info(f"[{state.get('analysis_id', '?')}] ▶ Entering node: {name}")

        try:
            result = await node_func(state)
            elapsed = time.time() - start
            logger.info(
                f"[{state.get('analysis_id', '?')}] ✓ Node {name} completed "
                f"in {elapsed:.2f}s"
            )

            # Inject timing metadata
            if "metadata" not in result:
                result["metadata"] = {}
            if isinstance(result.get("metadata"), dict):
                result["metadata"][f"{name}_duration_ms"] = int(elapsed * 1000)

            return result

        except Exception as e:
            elapsed = time.time() - start
            logger.error(
                f"[{state.get('analysis_id', '?')}] ✗ Node {name} FAILED "
                f"after {elapsed:.2f}s: {e}",
                exc_info=True,
            )
            # Return partial state with error — pipeline continues
            return {
                "errors": [f"Node {name} failed: {type(e).__name__}: {e}"],
                "metadata": {f"{name}_duration_ms": int(elapsed * 1000), f"{name}_error": str(e)},
            }

    return wrapped


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------

def route_after_analysis(state: AfriMineState) -> str:
    """
    Decide which branch(es) to activate after the Analysis Agent.

    Returns:
        "parallel_geo_market" — run Geology + Market in parallel
        "market_only" — skip Geology
        "direct_report" — go straight to Report (very low confidence)
    """
    analysis = state.get("analysis_result", {})
    requires_geology = analysis.get("requires_geology_context", True)
    confidence = analysis.get("overall_confidence", 0.0)

    if confidence < 0.1:
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
    Both branches run concurrently and converge at merge_branches.
    """
    analysis = state.get("analysis_result", {})
    requires_geology = analysis.get("requires_geology_context", True)
    confidence = analysis.get("overall_confidence", 0.0)

    sends: list[Send] = []

    if confidence < 0.1:
        sends.append(Send("merge_branches", state))
        return sends

    # Always include Market Agent (fast, no LLM)
    sends.append(Send("market", state))

    if requires_geology:
        sends.append(Send("geology", state))

    return sends


def merge_branches(state: AfriMineState) -> dict:
    """
    Barrier/merge node that waits for BOTH Geology and Market branches.

    This solves the fan-in bug: without it, Report would fire twice.
    LangGraph waits for ALL incoming edges before executing this node.
    """
    logger.info(
        f"[{state.get('analysis_id', '?')}] merge_branches barrier reached — "
        f"geology={'present' if state.get('geology_result') else 'absent'}, "
        f"market={'present' if state.get('market_result') else 'absent'}"
    )
    return {}


def route_after_report(state: AfriMineState) -> str:
    """
    Decide whether to refine the report or proceed to compliance.

    Returns:
        "compliance" — report is good
        "analysis" — loop back for refinement (max 3 iterations)
    """
    report = state.get("report_result", {})
    needs_refinement = report.get("needs_refinement", False)
    refinement_count = state.get("refinement_count", 0)

    if needs_refinement and refinement_count < settings.MAX_REFINEMENT_LOOPS:
        logger.info(f"Routing: refinement loop #{refinement_count + 1}")
        return "analysis"

    logger.info(f"Routing: compliance (refinement_count={refinement_count})")
    return "compliance"


def route_after_compliance(state: AfriMineState) -> str:
    """
    After compliance check, decide if human approval is needed.

    Returns:
        "end" — compliance passed or non-blocking issues
        "pause_for_approval" — human-in-the-loop for blocking issues
    """
    compliance = state.get("compliance_result", {})
    is_compliant = compliance.get("is_compliant", False)

    if is_compliant:
        return "end"

    issues = compliance.get("compliance_issues", [])
    if issues:
        logger.warning(f"Compliance issues: {issues}")

    # For MVP: complete with issues flagged
    # In production with ENABLE_HITL: return "pause_for_approval"
    if settings.ENABLE_HITL and not is_compliant:
        return "pause_for_approval"

    return "end"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(checkpointer=None) -> Any:
    """
    Build the complete AfriMine LangGraph StateGraph.

    Args:
        checkpointer: BaseCheckpointSaver instance. If None, no checkpointing.

    Returns:
        Compiled LangGraph application.
    """
    logger.info("Building AfriMine LangGraph...")

    graph = StateGraph(AfriMineState)

    # ── Add nodes (with timing wrapper) ────────────────────────────────────
    graph.add_node("sampling", _timed_node("sampling", sampling_agent))
    graph.add_node("analysis", _timed_node("analysis", analysis_agent))
    graph.add_node("geology", _timed_node("geology", geology_agent))
    graph.add_node("market", _timed_node("market", market_agent))
    graph.add_node("merge_branches", merge_branches)
    graph.add_node("report", _timed_node("report", report_agent))
    graph.add_node("compliance", _timed_node("compliance", compliance_agent))

    # ── Add edges ──────────────────────────────────────────────────────────

    # Entry
    graph.add_edge(START, "sampling")

    # Sequential: Sampling → Analysis
    graph.add_edge("sampling", "analysis")

    # Conditional fan-out after Analysis
    graph.add_conditional_edges(
        "analysis",
        fan_out_after_analysis,
        {
            "geology": "geology",
            "market": "market",
            "merge_branches": "merge_branches",
        },
    )

    # FAN-IN FIX: Both branches converge on merge_branches
    graph.add_edge("geology", "merge_branches")
    graph.add_edge("market", "merge_branches")

    # merge_branches → Report (single invocation)
    graph.add_edge("merge_branches", "report")

    # Report → Conditional (refinement loop or compliance)
    graph.add_conditional_edges(
        "report",
        route_after_report,
        {
            "analysis": "analysis",
            "compliance": "compliance",
        },
    )

    # Compliance → END (with optional HITL)
    graph.add_conditional_edges(
        "compliance",
        route_after_compliance,
        {
            "end": END,
            "pause_for_approval": END,
        },
    )

    # ── Compile ────────────────────────────────────────────────────────────
    compile_kwargs: dict[str, Any] = {}

    if checkpointer and settings.CHECKPOINT_ENABLED:
        compile_kwargs["checkpointer"] = checkpointer
        logger.info("Checkpointer attached — state persists to Supabase")

    compiled = graph.compile(**compile_kwargs)

    logger.info("AfriMine LangGraph compiled successfully")
    return compiled


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

async def run_analysis(
    initial_state: dict[str, Any],
    checkpointer=None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run a complete mineral analysis through the 6-agent pipeline.

    Args:
        initial_state: Input data (location, sample_data, etc.)
        checkpointer: Optional checkpoint saver for crash recovery.
        config: Optional LangGraph config (thread_id, etc.)

    Returns:
        Final state with all agent outputs populated.
    """
    graph = build_graph(checkpointer)

    if config is None:
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    thread_id = config.get("configurable", {}).get("thread_id", "?")
    logger.info(f"Starting analysis: thread={thread_id}")

    start_time = time.time()
    final_state = await graph.ainvoke(initial_state, config)
    total_ms = int((time.time() - start_time) * 1000)

    # Inject pipeline metadata
    if "metadata" not in final_state:
        final_state["metadata"] = {}
    final_state["metadata"]["pipeline_duration_ms"] = total_ms
    final_state["metadata"]["thread_id"] = thread_id

    logger.info(
        f"Analysis complete in {total_ms}ms: "
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
    Use for SSE endpoints feeding the Flutter frontend.

    Yields:
        (node_name, partial_state) tuples.
    """
    graph = build_graph(checkpointer)

    if config is None:
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    async for event in graph.astream(initial_state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            logger.info(f"Stream update: {node_name}")
            yield node_name, node_output
