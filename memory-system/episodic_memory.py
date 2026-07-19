"""
AfriMine AI — Episodic Memory

Records and retrieves past mineral analyses. Enables:
- "Find similar mineral samples" queries
- Analysis history browsing
- Confidence calibration from past results
- Pattern discovery across analysis episodes

Each episode = one complete 6-agent pipeline run.

Usage:
    em = EpisodicMemory(supabase_url="...", supabase_key="...")

    # Record a completed analysis
    analysis_id = em.record(
        session_id="sess-001",
        user_id="user-123",
        inputs={"location": {...}, "sample_data": {...}},
        outputs={"analysis_result": {...}, "geology_result": {...}, ...},
    )

    # Find similar past analyses
    similar = em.find_similar("gold-bearing quartz in migori greenstone belt", n=5)

    # Get full analysis
    analysis = em.get(analysis_id)
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Any, Optional
from datetime import datetime, timezone

import orjson

logger = logging.getLogger("afrimine.episodic")


class EpisodicMemory:
    """Manages episodic memory — records of past mineral analyses."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        vector_store=None,
    ):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY", "")
        self._client = None
        self._vector_store = vector_store

    @property
    def client(self):
        if self._client is None:
            from supabase import create_client
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    @property
    def vector_store(self):
        if self._vector_store is None:
            from vector_store import GeologicalVectorStore
            self._vector_store = GeologicalVectorStore(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
            )
        return self._vector_store

    # -------------------------------------------------------------------------
    # Record
    # -------------------------------------------------------------------------

    def record(
        self,
        session_id: str,
        user_id: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        pipeline_duration_ms: int | None = None,
    ) -> str:
        """
        Record a completed analysis in episodic memory.

        Args:
            session_id: The session this analysis belongs to
            user_id: User who initiated the analysis
            inputs: Original inputs (location, sample_data, etc.)
            outputs: All agent outputs (analysis_result, geology_result, etc.)

        Returns: analysis_id
        """
        analysis_id = str(uuid.uuid4())

        # Extract summary fields from outputs
        analysis_out = outputs.get("analysis_result", {})
        geology_out = outputs.get("geology_result", {})
        market_out = outputs.get("market_result", {})
        report_out = outputs.get("report_result", {})

        # Build the embedding text (what gets vectorized for similarity search)
        embedding_text = self._build_embedding_text(inputs, outputs)

        # Extract detected minerals
        detected_minerals = []
        if isinstance(analysis_out, dict):
            detected_minerals = analysis_out.get("detected_minerals", [])
            if not detected_minerals and analysis_out.get("mineral_type"):
                detected_minerals = [analysis_out["mineral_type"]]

        # Extract grade
        estimated_grade = None
        grade_unit = None
        if isinstance(analysis_out, dict):
            estimated_grade = analysis_out.get("estimated_grade")
            grade_unit = analysis_out.get("grade_unit", "ppm")

        # Extract confidence
        confidence_score = None
        if isinstance(analysis_out, dict):
            confidence_score = analysis_out.get("confidence")

        # Extract value
        estimated_value = None
        if isinstance(market_out, dict):
            estimated_value = market_out.get("estimated_value_usd")

        # Determine agents used
        agents_used = [k for k, v in outputs.items() if v is not None]

        # Build row
        row = {
            "analysis_id": analysis_id,
            "session_id": session_id,
            "user_id": user_id,
            "location": orjson.dumps(inputs.get("location", {})).decode(),
            "sample_data": orjson.dumps(inputs.get("sample_data", {})).decode(),
            "mineral_type": inputs.get("mineral_type") or (
                detected_minerals[0] if detected_minerals else None
            ),
            "sample_count": inputs.get("sample_count", 1),
            "sampling_output": orjson.dumps(outputs.get("sampling_result", {})).decode(),
            "analysis_output": orjson.dumps(analysis_out).decode(),
            "geology_output": orjson.dumps(geology_out).decode(),
            "market_output": orjson.dumps(market_out).decode(),
            "report_output": orjson.dumps(report_out).decode(),
            "compliance_output": orjson.dumps(outputs.get("compliance_result", {})).decode(),
            "detected_minerals": detected_minerals,
            "estimated_grade": estimated_grade,
            "grade_unit": grade_unit,
            "confidence_score": confidence_score,
            "estimated_value": estimated_value,
            "pipeline_duration_ms": pipeline_duration_ms,
            "agents_used": agents_used,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Insert into Supabase
        self.client.table("analysis_history").insert(row).execute()

        # Generate and store embedding (async-safe, but we do it inline)
        try:
            embedding = self.vector_store.embed(embedding_text)
            self.client.table("analysis_history").update({
                "embedding": embedding,
            }).eq("analysis_id", analysis_id).execute()
        except Exception as e:
            logger.warning("Failed to store embedding for analysis %s: %s", analysis_id, e)

        logger.info(
            "Recorded analysis %s: minerals=%s, confidence=%s",
            analysis_id, detected_minerals, confidence_score,
        )
        return analysis_id

    def _build_embedding_text(
        self, inputs: dict[str, Any], outputs: dict[str, Any]
    ) -> str:
        """
        Build a text representation of the analysis for embedding.
        Combines inputs + key outputs into a searchable description.
        """
        parts = []

        # Location
        loc = inputs.get("location", {})
        if isinstance(loc, dict):
            if loc.get("region"):
                parts.append(f"Region: {loc['region']}")
            if loc.get("country"):
                parts.append(f"Country: {loc['country']}")

        # Mineral type
        mineral = inputs.get("mineral_type")
        if mineral:
            parts.append(f"Mineral: {mineral}")

        # Analysis agent output
        analysis = outputs.get("analysis_result", {})
        if isinstance(analysis, dict):
            if analysis.get("description"):
                parts.append(analysis["description"])
            if analysis.get("detected_minerals"):
                parts.append(f"Detected: {', '.join(analysis['detected_minerals'])}")
            if analysis.get("rock_type"):
                parts.append(f"Rock type: {analysis['rock_type']}")

        # Geology agent output
        geology = outputs.get("geology_result", {})
        if isinstance(geology, dict):
            if geology.get("geological_context"):
                parts.append(geology["geological_context"])
            if geology.get("deposit_model"):
                parts.append(f"Deposit model: {geology['deposit_model']}")
            if geology.get("alteration"):
                parts.append(f"Alteration: {geology['alteration']}")

        # Sample description from field notes
        sample_data = inputs.get("sample_data", {})
        if isinstance(sample_data, dict):
            if sample_data.get("field_notes"):
                parts.append(sample_data["field_notes"])
            if sample_data.get("description"):
                parts.append(sample_data["description"])

        return " | ".join(parts) if parts else "mineral analysis"

    # -------------------------------------------------------------------------
    # Retrieve
    # -------------------------------------------------------------------------

    def find_similar(
        self,
        query: str,
        n: int = 10,
        mineral_filter: str | None = None,
        region_filter: str | None = None,
        min_confidence: float | None = None,
    ) -> list[dict]:
        """
        Find analyses similar to the query text.

        Uses pgvector cosine similarity via the find_similar_analyses SQL function.

        Args:
            query: Natural language description to search for
            n: Number of results to return
            mineral_filter: Only return analyses of this mineral type
            region_filter: Only return analyses from this region
            min_confidence: Minimum confidence score threshold

        Returns: list of analysis summaries with similarity scores
        """
        # Use vector store's search function
        results = self.vector_store.search_analyses(
            query=query,
            top_k=n,
            threshold=0.5,
            mineral_filter=mineral_filter,
            region_filter=region_filter,
        )

        # Apply confidence filter
        if min_confidence is not None:
            results = [r for r in results if (r.get("confidence_score") or 0) >= min_confidence]

        return results

    def get(self, analysis_id: str) -> dict | None:
        """Get a full analysis by ID."""
        result = (
            self.client.table("analysis_history")
            .select("*")
            .eq("analysis_id", analysis_id)
            .single()
            .execute()
        )
        if not result.data:
            return None

        row = result.data
        # Deserialize JSONB fields
        for field in [
            "location", "sample_data", "sampling_output", "analysis_output",
            "geology_output", "market_output", "report_output", "compliance_output",
        ]:
            if row.get(field) and isinstance(row[field], str):
                row[field] = orjson.loads(row[field])

        # Remove embedding from response (large, not needed for display)
        row.pop("embedding", None)

        return row

    def get_by_user(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        mineral_type: str | None = None,
    ) -> list[dict]:
        """Get recent analyses for a user."""
        query = (
            self.client.table("analysis_history")
            .select(
                "analysis_id, mineral_type, detected_minerals, estimated_grade, "
                "grade_unit, confidence_score, estimated_value, data_quality, "
                "validation_status, pipeline_duration_ms, created_at"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if mineral_type:
            query = query.eq("mineral_type", mineral_type)

        result = query.execute()
        return result.data or []

    def get_by_region(
        self,
        region: str,
        limit: int = 50,
    ) -> list[dict]:
        """Get analyses from a specific region."""
        result = (
            self.client.table("analysis_history")
            .select(
                "analysis_id, mineral_type, detected_minerals, estimated_grade, "
                "confidence_score, location, created_at"
            )
            .eq("location->>'region'", region)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def get_confidence_distribution(
        self,
        mineral_type: str | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """
        Get confidence score distribution for calibration.
        Returns: {mean, median, std, count, scores}
        """
        query = (
            self.client.table("analysis_history")
            .select("confidence_score")
            .not_.is_("confidence_score", "null")
        )

        if mineral_type:
            query = query.eq("mineral_type", mineral_type)
        if region:
            query = query.eq("location->>'region'", region)

        result = query.execute()
        scores = [r["confidence_score"] for r in (result.data or [])]

        if not scores:
            return {"mean": 0, "median": 0, "std": 0, "count": 0, "scores": []}

        import numpy as np
        arr = np.array(scores)
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr)),
            "count": len(scores),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
        }

    # -------------------------------------------------------------------------
    # Validation & Feedback
    # -------------------------------------------------------------------------

    def validate(
        self,
        analysis_id: str,
        status: str,
        validator_notes: str | None = None,
    ) -> None:
        """Update validation status of an analysis (geologist feedback)."""
        self.client.table("analysis_history").update({
            "validation_status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("analysis_id", analysis_id).execute()

    def mark_anomalous(self, analysis_id: str, reason: str) -> None:
        """Flag an analysis as anomalous (for pattern detection)."""
        self.client.table("analysis_history").update({
            "is_anomalous": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("analysis_id", analysis_id).execute()
