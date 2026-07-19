"""
AfriMine AI — Main Entry Point
================================

Initialize the LangGraph pipeline, run analysis, return results.

Usage:
    # As module
    python -m main

    # As library
    from main import AfriMinePipeline
    pipeline = AfriMinePipeline()
    result = await pipeline.analyze(location, sample_data, user_id)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from typing import Any

from config import settings
from graph import build_graph, run_analysis, stream_analysis
from memory.checkpointer import create_checkpointer, get_checkpointer_config
from state import build_initial_state, validate_state_inputs

logger = logging.getLogger("afrimine.main")


class AfriMinePipeline:
    """
    High-level interface for the AfriMine AI analysis pipeline.

    Usage:
        pipeline = AfriMinePipeline()

        result = await pipeline.analyze(
            location={"lat": -1.05, "lon": 34.55, "region": "Nyatike", "county": "Migori"},
            sample_data={"sample_id": "NYA-001", "xrf_readings": {"Au": 5.2, "As": 120}},
            user_id="user-123",
        )

        print(result["compliance_result"]["is_compliant"])
        print(result["market_result"]["deposit_value_estimate_usd"])
    """

    def __init__(self, use_memory_checkpointer: bool = False):
        """
        Initialize the pipeline.

        Args:
            use_memory_checkpointer: Use in-memory checkpointer (for testing).
        """
        self._checkpointer = create_checkpointer(use_memory=use_memory_checkpointer)
        self._graph = None

        # Log config warnings
        warnings = settings.validate()
        for w in warnings:
            logger.warning(f"Config: {w}")

    @property
    def graph(self):
        """Lazy-build the graph on first use."""
        if self._graph is None:
            self._graph = build_graph(checkpointer=self._checkpointer)
        return self._graph

    async def analyze(
        self,
        location: dict[str, Any],
        sample_data: dict[str, Any],
        user_id: str,
        analysis_id: str | None = None,
        satellite_imagery: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run a complete mineral analysis.

        Args:
            location: GPS and region info. Keys: lat, lon, region, county, country.
            sample_data: Sample metadata. Keys: sample_id, xrf_readings, notes, photo_url.
            user_id: Supabase auth user ID.
            analysis_id: Optional unique ID (auto-generated if not provided).
            satellite_imagery: Optional base64 or URL to Sentinel-2 tile.
            metadata: Optional metadata dict.

        Returns:
            Final state dict with all agent outputs.

        Raises:
            ValueError: If input validation fails.
        """
        analysis_id = analysis_id or str(uuid.uuid4())

        # Build initial state
        state = build_initial_state(
            analysis_id=analysis_id,
            user_id=user_id,
            location=location,
            sample_data=sample_data,
            satellite_imagery=satellite_imagery,
            metadata=metadata,
        )

        # Validate inputs
        errors = validate_state_inputs(state)
        if errors:
            raise ValueError(f"Invalid inputs: {'; '.join(errors)}")

        # Run pipeline
        config = get_checkpointer_config(analysis_id)
        return await run_analysis(state, checkpointer=self._checkpointer, config=config)

    async def stream(
        self,
        location: dict[str, Any],
        sample_data: dict[str, Any],
        user_id: str,
        analysis_id: str | None = None,
    ):
        """
        Stream analysis progress (for SSE endpoints).

        Yields:
            (node_name, partial_state) tuples as agents complete.
        """
        analysis_id = analysis_id or str(uuid.uuid4())

        state = build_initial_state(
            analysis_id=analysis_id,
            user_id=user_id,
            location=location,
            sample_data=sample_data,
        )

        errors = validate_state_inputs(state)
        if errors:
            raise ValueError(f"Invalid inputs: {'; '.join(errors)}")

        config = get_checkpointer_config(analysis_id)
        async for node_name, partial in stream_analysis(state, self._checkpointer, config):
            yield node_name, partial

    async def resume(self, analysis_id: str) -> dict[str, Any] | None:
        """
        Resume a paused/failed analysis from its last checkpoint.

        Args:
            analysis_id: The analysis thread ID.

        Returns:
            Final state if completed, None if no checkpoint found.
        """
        config = get_checkpointer_config(analysis_id)

        try:
            # Invoke with None input to resume from checkpoint
            result = await self.graph.ainvoke(None, config)
            return result
        except Exception as e:
            logger.error(f"Failed to resume analysis {analysis_id}: {e}")
            return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _cli_main():
    """CLI entry point for testing the pipeline."""
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("AfriMine AI — Pipeline Test")
    logger.info(f"Model: {settings.GEMINI_MODEL}")
    logger.info(f"Checkpoint: {'Supabase' if settings.SUPABASE_URL else 'In-memory'}")

    pipeline = AfriMinePipeline(use_memory_checkpointer=True)

    test_state = {
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
    }

    try:
        result = await pipeline.analyze(
            location=test_state["location"],
            sample_data=test_state["sample_data"],
            user_id="test-user",
            analysis_id="test-001",
        )

        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)

        compliance = result.get("compliance_result", {})
        market = result.get("market_result", {})
        report = result.get("report_result", {})
        errors = result.get("errors", [])
        metadata = result.get("metadata", {})

        print(f"Compliant: {compliance.get('is_compliant')}")
        print(f"License needed: {compliance.get('license_type_required', 'N/A')}")
        print(f"Gold price: ${market.get('gold_price_usd_oz', 0):,.2f}/oz")
        print(f"Deposit value: ${market.get('deposit_value_estimate_usd', 0):,.0f} NPV")
        print(f"Cut-off grade: {market.get('cut_off_grade_gpt', 0):.2f} g/t")
        print(f"Recommendation: {report.get('recommendation', 'N/A')}")
        print(f"Pipeline time: {metadata.get('pipeline_duration_ms', '?')}ms")
        print(f"Errors: {errors if errors else 'None'}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_cli_main())
