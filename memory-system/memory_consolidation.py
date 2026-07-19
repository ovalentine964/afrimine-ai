"""
AfriMine AI — Memory Consolidation Engine

Background jobs that move data between memory layers:

1. SHORT-TERM → EPISODIC
   After an analysis completes, consolidate the session state into
   a permanent episodic memory record.

2. EPISODIC → SEMANTIC
   Batch: embed new analysis summaries for vector search.

3. PATTERN DISCOVERY
   Weekly: scan analysis history for recurring patterns
   (element correlations, grade distributions, spatial clusters).

4. WORKFLOW LEARNING
   After a successful analysis, extract the agent sequence as a
   reusable workflow template.

5. CLEANUP
   Expire old sessions, prune low-confidence patterns, archive
   old checkpoint data.

Usage:
    # Run as a background job (APScheduler or cron)
    from memory_consolidation import MemoryConsolidation

    mc = MemoryConsolidation()
    mc.run_all()  # Run all consolidation jobs

    # Or run specific jobs
    mc.consolidate_sessions()   # Short-term → Episodic
    mc.embed_new_analyses()     # Episodic → Semantic
    mc.discover_patterns()      # Pattern discovery
    mc.learn_workflows()        # Workflow extraction
    mc.cleanup()                # Expire old data
"""

from __future__ import annotations

import os
import logging
from typing import Any
from datetime import datetime, timezone, timedelta

import orjson

logger = logging.getLogger("afrimine.consolidation")


class MemoryConsolidation:
    """
    Background consolidation engine for the layered memory system.

    Runs periodically (via APScheduler or cron) to:
    - Move completed sessions to episodic memory
    - Embed new analyses for vector search
    - Discover patterns across analyses
    - Extract reusable workflows
    - Clean up expired data
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        google_api_key: str | None = None,
    ):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY", "")
        self._client = None
        self._memory_manager = None
        self._vector_store = None

    @property
    def client(self):
        if self._client is None:
            from supabase import create_client
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    @property
    def memory_manager(self):
        if self._memory_manager is None:
            from memory_manager import MemoryManager
            self._memory_manager = MemoryManager(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
            )
        return self._memory_manager

    @property
    def vector_store(self):
        if self._vector_store is None:
            from vector_store import GeologicalVectorStore
            self._vector_store = GeologicalVectorStore(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
            )
        return self._vector_store

    # =========================================================================
    # JOB 1: Consolidate Sessions → Episodic Memory
    # =========================================================================

    def consolidate_sessions(self) -> int:
        """
        Move completed sessions to episodic memory.

        Finds sessions with status='completed' that haven't been consolidated,
        creates analysis_history records from their state, and marks them as
        consolidated.

        Returns: number of sessions consolidated.
        """
        # Find completed sessions not yet in analysis_history
        result = (
            self.client.table("agent_sessions")
            .select("*")
            .eq("status", "completed")
            .is_("completed_at", "not.null")
            .order("completed_at", desc=False)
            .limit(50)
            .execute()
        )

        sessions = result.data or []
        consolidated = 0

        for session in sessions:
            session_id = session["session_id"]

            # Check if already consolidated
            existing = (
                self.client.table("analysis_history")
                .select("analysis_id")
                .eq("session_id", session_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                # Already consolidated, mark session
                self.client.table("agent_sessions").update({
                    "status": "consolidated",
                }).eq("session_id", session_id).execute()
                continue

            # Extract state
            state = session.get("state", {})
            if isinstance(state, str):
                state = orjson.loads(state)

            # Build inputs from session state
            inputs = {
                "location": session.get("location") or state.get("location", {}),
                "sample_data": state.get("sample_data", {}),
                "mineral_type": session.get("mineral_type") or state.get("mineral_type"),
            }

            # Build outputs from agent results
            outputs = {}
            for agent in ["sampling", "analysis", "geology", "market", "report", "compliance"]:
                key = f"{agent}_result"
                if key in state:
                    outputs[key] = state[key]

            if not outputs:
                logger.debug("Session %s has no agent outputs, skipping", session_id)
                continue

            # Record in episodic memory
            try:
                self.memory_manager.record_analysis(
                    session_id=session_id,
                    user_id=session.get("user_id", "system"),
                    inputs=inputs,
                    outputs=outputs,
                )
                consolidated += 1
                logger.info("Consolidated session %s → episodic memory", session_id)
            except Exception as e:
                logger.error("Failed to consolidate session %s: %s", session_id, e)

        return consolidated

    # =========================================================================
    # JOB 2: Embed New Analyses (Episodic → Semantic)
    # =========================================================================

    def embed_new_analyses(self) -> int:
        """
        Generate embeddings for analyses that don't have them yet.

        Returns: number of analyses embedded.
        """
        # Find analyses without embeddings
        result = (
            self.client.table("analysis_history")
            .select("analysis_id, location, sample_data, analysis_output, geology_output")
            .is_("embedding", "null")
            .limit(100)
            .execute()
        )

        analyses = result.data or []
        if not analyses:
            return 0

        # Build embedding texts
        ids = []
        texts = []
        for a in analyses:
            parts = []
            loc = a.get("location", {})
            if isinstance(loc, str):
                loc = orjson.loads(loc)
            if loc.get("region"):
                parts.append(f"Region: {loc['region']}")

            analysis_out = a.get("analysis_output", {})
            if isinstance(analysis_out, str):
                analysis_out = orjson.loads(analysis_out)
            if analysis_out.get("description"):
                parts.append(analysis_out["description"])
            if analysis_out.get("detected_minerals"):
                parts.append(f"Minerals: {', '.join(analysis_out['detected_minerals'])}")

            geology_out = a.get("geology_output", {})
            if isinstance(geology_out, str):
                geology_out = orjson.loads(geology_out)
            if geology_out.get("geological_context"):
                parts.append(geology_out["geological_context"])

            text = " | ".join(parts) if parts else "mineral analysis"
            ids.append(a["analysis_id"])
            texts.append(text)

        # Batch embed and store
        count = self.vector_store.add_batch(
            table="analysis_history",
            ids=ids,
            texts=texts,
            id_column="analysis_id",
        )

        logger.info("Embedded %d new analyses", count)
        return count

    # =========================================================================
    # JOB 3: Pattern Discovery
    # =========================================================================

    def discover_patterns(self) -> int:
        """
        Discover patterns across validated analyses.

        Finds:
        - Element correlations (pathfinder → target mineral)
        - Grade distributions per mineral/region
        - Anomalous analyses

        Returns: number of patterns discovered/updated.
        """
        from knowledge_graph import GeologicalKnowledgeGraph
        kg = GeologicalKnowledgeGraph(
            supabase_url=self.supabase_url,
            supabase_key=self.supabase_key,
            vector_store=self.vector_store,
        )

        patterns_found = 0

        # Discover patterns per mineral type
        minerals_result = (
            self.client.table("analysis_history")
            .select("mineral_type")
            .not_.is_("mineral_type", "null")
            .execute()
        )
        minerals = set(r["mineral_type"] for r in (minerals_result.data or []))

        for mineral in minerals:
            patterns = kg.discover_patterns(mineral=mineral, min_support=3)

            for pattern in patterns:
                # Check if pattern already exists
                existing = (
                    self.client.table("mineral_patterns")
                    .select("pattern_id, support_count, confidence")
                    .eq("pattern_type", pattern["pattern_type"])
                    .eq("name", pattern["name"])
                    .execute()
                )

                if existing.data:
                    # Update existing pattern
                    old = existing.data[0]
                    self.client.table("mineral_patterns").update({
                        "support_count": pattern["support_count"],
                        "confidence": pattern["confidence"],
                        "conditions": orjson.dumps(pattern["conditions"]).decode(),
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    }).eq("pattern_id", old["pattern_id"]).execute()
                else:
                    # Create new pattern
                    import uuid
                    self.client.table("mineral_patterns").insert({
                        "pattern_id": str(uuid.uuid4()),
                        "pattern_type": pattern["pattern_type"],
                        "name": pattern["name"],
                        "description": pattern["description"],
                        "conditions": orjson.dumps(pattern["conditions"]).decode(),
                        "support_count": pattern["support_count"],
                        "confidence": pattern["confidence"],
                        "applicable_regions": [],
                        "status": "proposed",
                        "first_observed": datetime.now(timezone.utc).isoformat(),
                    }).execute()

                patterns_found += 1

        logger.info("Discovered/updated %d patterns", patterns_found)
        return patterns_found

    # =========================================================================
    # JOB 4: Workflow Learning
    # =========================================================================

    def learn_workflows(self) -> int:
        """
        Extract reusable workflow templates from successful analyses.

        Finds validated analyses with high confidence and extracts their
        agent execution sequence as a reusable workflow.

        Returns: number of workflows learned.
        """
        # Find successful analyses that aren't already workflow sources
        result = (
            self.client.table("analysis_history")
            .select("*")
            .eq("validation_status", "validated")
            .gte("confidence_score", 0.75)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )

        analyses = result.data or []
        learned = 0

        for analysis in analyses:
            analysis_id = analysis["analysis_id"]
            mineral = analysis.get("mineral_type")
            agents = analysis.get("agents_used") or []

            if not agents:
                continue

            # Check if workflow already exists for this analysis
            existing = (
                self.client.table("learned_workflows")
                .select("workflow_id")
                .eq("source_analysis", analysis_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue

            # Extract region from location
            location = analysis.get("location", {})
            if isinstance(location, str):
                location = orjson.loads(location)
            region = location.get("region")

            # Build workflow graph definition
            graph_def = {
                "nodes": [
                    {"id": agent, "type": "agent"} for agent in agents
                ],
                "edges": [
                    {"from": agents[i], "to": agents[i + 1]}
                    for i in range(len(agents) - 1)
                ],
                "conditions": {},
            }

            # Check if parallel execution was used
            output_keys = [k for k in analysis.keys() if k.endswith("_output") and analysis.get(k)]
            if "geology_output" in [k for k in output_keys] and "market_output" in [k for k in output_keys]:
                # Likely parallel geology + market
                graph_def["parallel_groups"] = [["geology", "market"]]

            # Save workflow
            import uuid
            workflow_id = str(uuid.uuid4())
            self.client.table("learned_workflows").insert({
                "workflow_id": workflow_id,
                "name": f"{mineral or 'general'}_analysis_{analysis_id[:8]}",
                "description": (
                    f"Learned from analysis {analysis_id[:8]}: "
                    f"{mineral or 'unknown mineral'} in {region or 'unknown region'}"
                ),
                "workflow_type": "full_pipeline",
                "graph_definition": orjson.dumps(graph_def).decode(),
                "applicable_minerals": [mineral] if mineral else [],
                "applicable_regions": [region] if region else [],
                "required_agents": agents,
                "source_analysis": analysis_id,
                "avg_duration_ms": analysis.get("pipeline_duration_ms"),
                "success_rate": analysis.get("confidence_score"),
                "avg_confidence": analysis.get("confidence_score"),
                "status": "active",
            }).execute()

            learned += 1

        logger.info("Learned %d new workflows", learned)
        return learned

    # =========================================================================
    # JOB 5: Cleanup
    # =========================================================================

    def cleanup(self) -> dict[str, int]:
        """
        Clean up expired and low-value data.

        - Expire sessions past their TTL
        - Archive old checkpoint data
        - Remove deprecated patterns

        Returns: {table: count_deleted}
        """
        stats = {}

        # 1. Expire old sessions
        expired = self.memory_manager.cleanup_expired()
        stats["expired_sessions"] = expired

        # 2. Delete checkpoint data for expired sessions (>7 days old)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        # Find old checkpoint thread_ids
        old_threads = (
            self.client.table("agent_sessions")
            .select("session_id")
            .eq("status", "expired")
            .lt("expires_at", cutoff)
            .limit(100)
            .execute()
        )

        deleted_checkpoints = 0
        for thread in (old_threads.data or []):
            tid = thread["session_id"]
            self.client.table("checkpoint_writes").delete().eq("thread_id", tid).execute()
            self.client.table("checkpoints").delete().eq("thread_id", tid).execute()
            deleted_checkpoints += 1

        stats["deleted_checkpoint_threads"] = deleted_checkpoints

        # 3. Delete expired long-term memory entries
        self.client.table("agent_long_term_memory").delete().lt(
            "expires_at", datetime.now(timezone.utc).isoformat()
        ).is_("expires_at", "not.null").execute()
        stats["expired_ltm"] = 0  # Can't easily count with Supabase client

        logger.info("Cleanup complete: %s", stats)
        return stats

    # =========================================================================
    # Run All
    # =========================================================================

    def run_all(self) -> dict[str, Any]:
        """
        Run all consolidation jobs. Returns summary.

        Call this periodically (e.g., every hour via APScheduler).
        """
        results = {}
        start = datetime.now(timezone.utc)

        try:
            results["consolidated_sessions"] = self.consolidate_sessions()
        except Exception as e:
            logger.error("Session consolidation failed: %s", e)
            results["consolidated_sessions_error"] = str(e)

        try:
            results["embedded_analyses"] = self.embed_new_analyses()
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            results["embedding_error"] = str(e)

        try:
            results["discovered_patterns"] = self.discover_patterns()
        except Exception as e:
            logger.error("Pattern discovery failed: %s", e)
            results["pattern_error"] = str(e)

        try:
            results["learned_workflows"] = self.learn_workflows()
        except Exception as e:
            logger.error("Workflow learning failed: %s", e)
            results["workflow_error"] = str(e)

        try:
            results["cleanup"] = self.cleanup()
        except Exception as e:
            logger.error("Cleanup failed: %s", e)
            results["cleanup_error"] = str(e)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)

        logger.info("Consolidation run complete in %.1fs: %s", elapsed, results)
        return results


# =============================================================================
# APScheduler Integration
# =============================================================================

def start_consolidation_scheduler(
    supabase_url: str | None = None,
    supabase_key: str | None = None,
):
    """
    Start the APScheduler-based consolidation scheduler.

    Schedule:
    - Every 15 minutes: consolidate sessions, embed analyses
    - Every 6 hours: discover patterns, learn workflows
    - Daily at 3am: cleanup
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    mc = MemoryConsolidation(supabase_url=supabase_url, supabase_key=supabase_key)
    scheduler = BackgroundScheduler()

    # Frequent jobs (every 15 min)
    scheduler.add_job(
        mc.consolidate_sessions,
        "interval",
        minutes=15,
        id="consolidate_sessions",
        replace_existing=True,
    )
    scheduler.add_job(
        mc.embed_new_analyses,
        "interval",
        minutes=15,
        id="embed_analyses",
        replace_existing=True,
    )

    # Medium frequency (every 6 hours)
    scheduler.add_job(
        mc.discover_patterns,
        "interval",
        hours=6,
        id="discover_patterns",
        replace_existing=True,
    )
    scheduler.add_job(
        mc.learn_workflows,
        "interval",
        hours=6,
        id="learn_workflows",
        replace_existing=True,
    )

    # Daily cleanup at 3am
    scheduler.add_job(
        mc.cleanup,
        "cron",
        hour=3,
        minute=0,
        id="cleanup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Consolidation scheduler started")
    return scheduler


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    mc = MemoryConsolidation()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "consolidate":
            print(f"Consolidated: {mc.consolidate_sessions()}")
        elif command == "embed":
            print(f"Embedded: {mc.embed_new_analyses()}")
        elif command == "patterns":
            print(f"Patterns: {mc.discover_patterns()}")
        elif command == "workflows":
            print(f"Workflows: {mc.learn_workflows()}")
        elif command == "cleanup":
            print(f"Cleanup: {mc.cleanup()}")
        elif command == "run-all":
            print(f"Results: {mc.run_all()}")
        elif command == "scheduler":
            scheduler = start_consolidation_scheduler()
            print("Scheduler running. Press Ctrl+C to stop.")
            try:
                import time
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                scheduler.shutdown()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python memory_consolidation.py [consolidate|embed|patterns|workflows|cleanup|run-all|scheduler]")
    else:
        print(f"Results: {mc.run_all()}")
