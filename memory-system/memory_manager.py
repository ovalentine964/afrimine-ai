"""
AfriMine AI — Memory Manager
Unified entry point for all memory layers.

Usage:
    from memory_manager import MemoryManager

    mm = MemoryManager()

    # Short-term: save/load agent session state
    mm.save_session(session_id, state)
    state = mm.load_session(session_id)

    # Episodic: record and retrieve past analyses
    mm.record_analysis(session_id, user_id, inputs, outputs)
    similar = mm.find_similar_analyses("gold-bearing quartz in migori", n=5)

    # Semantic: query geological knowledge
    knowledge = mm.query_knowledge("pathfinder elements for gold", category="pathfinder_element")

    # Procedural: save/retrieve successful workflows
    mm.save_workflow("gold_analysis_v2", graph_def, metadata)
    workflows = mm.get_applicable_workflows(mineral="gold", region="migori_belt")

    # Long-term: store/retrieve persistent facts
    mm.remember("region:migori_belt", "avg_gold_grade", {"ppm": 2.3, "n": 45})
    fact = mm.recall("region:migori_belt", "avg_gold_grade")
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Any, Optional
from datetime import datetime, timezone

import orjson

logger = logging.getLogger("afrimine.memory")


class MemoryManager:
    """
    Unified interface to all AfriMine AI memory layers.

    Layers:
        1. Short-term  — session state (via SupabaseCheckpointer)
        2. Episodic    — analysis history (via EpisodicMemory)
        3. Semantic    — knowledge + embeddings (via VectorStore, KnowledgeGraph)
        4. Procedural  — learned workflows
        5. Long-term   — persistent facts
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        google_api_key: str | None = None,
    ):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY", "")
        self.google_api_key = google_api_key or os.environ.get("GOOGLE_API_KEY", "")

        # Lazy-initialized sub-modules (import here to avoid circular deps)
        self._checkpointer = None
        self._vector_store = None
        self._episodic = None
        self._knowledge_graph = None
        self._supabase = None

    # -------------------------------------------------------------------------
    # Lazy property accessors
    # -------------------------------------------------------------------------

    @property
    def supabase(self):
        if self._supabase is None:
            from supabase import create_client
            self._supabase = create_client(self.supabase_url, self.supabase_key)
        return self._supabase

    @property
    def checkpointer(self):
        if self._checkpointer is None:
            from supabase_checkpointer import SupabaseCheckpointer
            self._checkpointer = SupabaseCheckpointer(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
            )
        return self._checkpointer

    @property
    def vector_store(self):
        if self._vector_store is None:
            from vector_store import GeologicalVectorStore
            self._vector_store = GeologicalVectorStore(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
            )
        return self._vector_store

    @property
    def episodic(self):
        if self._episodic is None:
            from episodic_memory import EpisodicMemory
            self._episodic = EpisodicMemory(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
                vector_store=self.vector_store,
            )
        return self._episodic

    @property
    def knowledge_graph(self):
        if self._knowledge_graph is None:
            from knowledge_graph import GeologicalKnowledgeGraph
            self._knowledge_graph = GeologicalKnowledgeGraph(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
                vector_store=self.vector_store,
            )
        return self._knowledge_graph

    # =========================================================================
    # LAYER 1: SHORT-TERM MEMORY (Session State)
    # =========================================================================

    def save_session(
        self,
        session_id: str,
        state: dict[str, Any],
        pipeline_run_id: str | None = None,
        user_id: str = "system",
        location: dict | None = None,
        mineral_type: str | None = None,
    ) -> None:
        """Save current agent session state."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "session_id": session_id,
            "pipeline_run_id": pipeline_run_id or session_id,
            "user_id": user_id,
            "status": "active",
            "state": orjson.dumps(state).decode(),
            "state_version": 1,
            "location": orjson.dumps(location).decode() if location else None,
            "mineral_type": mineral_type,
            "updated_at": now,
        }

        # Upsert: insert or update on conflict
        existing = (
            self.supabase.table("agent_sessions")
            .select("state_version")
            .eq("session_id", session_id)
            .execute()
        )

        if existing.data:
            current_version = existing.data[0]["state_version"]
            data["state_version"] = current_version + 1
            result = (
                self.supabase.table("agent_sessions")
                .update(data)
                .eq("session_id", session_id)
                .eq("state_version", current_version)  # Optimistic concurrency
                .execute()
            )
            if not result.data:
                logger.warning("Concurrent write conflict for session %s", session_id)
        else:
            self.supabase.table("agent_sessions").insert(data).execute()

        logger.debug("Saved session %s (v%d)", session_id, data["state_version"])

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Load agent session state. Returns None if not found."""
        result = (
            self.supabase.table("agent_sessions")
            .select("state, status")
            .eq("session_id", session_id)
            .single()
            .execute()
        )

        if not result.data or result.data["status"] == "expired":
            return None

        return orjson.loads(result.data["state"])

    def mark_agent_complete(self, session_id: str, agent_name: str) -> None:
        """Record that an agent has completed its step."""
        result = (
            self.supabase.table("agent_sessions")
            .select("agents_completed, current_agent")
            .eq("session_id", session_id)
            .single()
            .execute()
        )
        if not result.data:
            return

        completed = result.data.get("agents_completed") or []
        if agent_name not in completed:
            completed.append(agent_name)

        self.supabase.table("agent_sessions").update({
            "agents_completed": completed,
            "current_agent": agent_name,
        }).eq("session_id", session_id).execute()

    def complete_session(self, session_id: str) -> None:
        """Mark a session as completed."""
        self.supabase.table("agent_sessions").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("session_id", session_id).execute()

    # =========================================================================
    # LAYER 2: EPISODIC MEMORY (Analysis History)
    # =========================================================================

    def record_analysis(
        self,
        session_id: str,
        user_id: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        pipeline_duration_ms: int | None = None,
    ) -> str:
        """Record a completed analysis in episodic memory. Returns analysis_id."""
        return self.episodic.record(
            session_id=session_id,
            user_id=user_id,
            inputs=inputs,
            outputs=outputs,
            pipeline_duration_ms=pipeline_duration_ms,
        )

    def find_similar_analyses(
        self,
        query: str,
        n: int = 10,
        mineral_filter: str | None = None,
        region_filter: str | None = None,
    ) -> list[dict]:
        """Find analyses similar to the query text."""
        return self.episodic.find_similar(
            query=query,
            n=n,
            mineral_filter=mineral_filter,
            region_filter=region_filter,
        )

    def get_analysis(self, analysis_id: str) -> dict | None:
        """Get a specific analysis by ID."""
        return self.episodic.get(analysis_id)

    def get_user_analyses(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[dict]:
        """Get recent analyses for a user."""
        return self.episodic.get_by_user(user_id, limit=limit, offset=offset)

    # =========================================================================
    # LAYER 3: SEMANTIC MEMORY (Knowledge + Patterns)
    # =========================================================================

    def query_knowledge(
        self,
        query: str,
        category: str | None = None,
        n: int = 5,
    ) -> list[dict]:
        """Query the geological knowledge base."""
        return self.knowledge_graph.search(query, category=category, n=n)

    def add_knowledge(
        self,
        category: str,
        title: str,
        description: str,
        content: dict,
        related_minerals: list[str] | None = None,
        source: str | None = None,
    ) -> str:
        """Add knowledge to the geological knowledge base."""
        return self.knowledge_graph.add(
            category=category,
            title=title,
            description=description,
            content=content,
            related_minerals=related_minerals,
            source=source,
        )

    def discover_patterns(
        self,
        mineral: str | None = None,
        region: str | None = None,
        min_support: int = 3,
    ) -> list[dict]:
        """Discover patterns across analyses."""
        return self.knowledge_graph.discover_patterns(
            mineral=mineral,
            region=region,
            min_support=min_support,
        )

    # =========================================================================
    # LAYER 4: PROCEDURAL MEMORY (Learned Workflows)
    # =========================================================================

    def save_workflow(
        self,
        name: str,
        graph_definition: dict,
        workflow_type: str = "full_pipeline",
        applicable_minerals: list[str] | None = None,
        applicable_regions: list[str] | None = None,
        required_agents: list[str] | None = None,
        source_analysis: str | None = None,
    ) -> str:
        """Save a successful workflow for future reuse."""
        workflow_id = str(uuid.uuid4())
        data = {
            "workflow_id": workflow_id,
            "name": name,
            "description": f"Learned workflow: {name}",
            "workflow_type": workflow_type,
            "graph_definition": orjson.dumps(graph_definition).decode(),
            "applicable_minerals": applicable_minerals or [],
            "applicable_regions": applicable_regions or [],
            "required_agents": required_agents or [
                "sampling", "analysis", "geology", "market", "report", "compliance"
            ],
            "source_analysis": source_analysis,
            "status": "active",
        }
        self.supabase.table("learned_workflows").insert(data).execute()
        logger.info("Saved workflow %s (%s)", name, workflow_id)
        return workflow_id

    def get_applicable_workflows(
        self,
        mineral: str | None = None,
        region: str | None = None,
        workflow_type: str | None = None,
    ) -> list[dict]:
        """Find workflows applicable to a given mineral/region."""
        query = self.supabase.table("learned_workflows").select("*").eq("status", "active")

        if workflow_type:
            query = query.eq("workflow_type", workflow_type)

        result = query.execute()
        workflows = result.data or []

        # Filter by mineral/region (array containment)
        applicable = []
        for wf in workflows:
            minerals = wf.get("applicable_minerals") or []
            regions = wf.get("applicable_regions") or []

            mineral_match = not mineral or not minerals or mineral in minerals
            region_match = not region or not regions or region in regions

            if mineral_match and region_match:
                applicable.append(wf)

        # Sort by success rate (best first)
        applicable.sort(key=lambda w: w.get("success_rate") or 0, reverse=True)
        return applicable

    def record_workflow_outcome(
        self,
        workflow_id: str,
        success: bool,
        duration_ms: int,
        confidence: float,
    ) -> None:
        """Update workflow statistics after a run."""
        result = (
            self.supabase.table("learned_workflows")
            .select("times_used, avg_duration_ms, success_rate, avg_confidence")
            .eq("workflow_id", workflow_id)
            .single()
            .execute()
        )
        if not result.data:
            return

        wf = result.data
        n = (wf.get("times_used") or 0) + 1
        old_dur = wf.get("avg_duration_ms") or duration_ms
        old_sr = wf.get("success_rate") or (1.0 if success else 0.0)
        old_conf = wf.get("avg_confidence") or confidence

        # Running average
        new_dur = int(old_dur + (duration_ms - old_dur) / n)
        new_sr = old_sr + ((1.0 if success else 0.0) - old_sr) / n
        new_conf = old_conf + (confidence - old_conf) / n

        self.supabase.table("learned_workflows").update({
            "times_used": n,
            "avg_duration_ms": new_dur,
            "success_rate": round(new_sr, 4),
            "avg_confidence": round(new_conf, 4),
            "last_used": datetime.now(timezone.utc).isoformat(),
        }).eq("workflow_id", workflow_id).execute()

    # =========================================================================
    # LAYER 5: LONG-TERM MEMORY (Persistent Facts)
    # =========================================================================

    def remember(
        self,
        namespace: str,
        key: str,
        value: Any,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> None:
        """Store a persistent fact in long-term memory."""
        data = {
            "memory_id": str(uuid.uuid4()),
            "namespace": namespace,
            "key": key,
            "value": orjson.dumps(value).decode(),
            "confidence": confidence,
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Upsert on (namespace, key)
        self.supabase.table("agent_long_term_memory").upsert(
            data,
            on_conflict="namespace,key",
        ).execute()
        logger.debug("Remembered %s:%s", namespace, key)

    def recall(self, namespace: str, key: str) -> Any | None:
        """Retrieve a fact from long-term memory."""
        result = (
            self.supabase.table("agent_long_term_memory")
            .select("value, confidence")
            .eq("namespace", namespace)
            .eq("key", key)
            .single()
            .execute()
        )
        if not result.data:
            return None

        # Check expiry
        return orjson.loads(result.data["value"])

    def recall_namespace(self, namespace: str) -> dict[str, Any]:
        """Retrieve all facts in a namespace."""
        result = (
            self.supabase.table("agent_long_term_memory")
            .select("key, value")
            .eq("namespace", namespace)
            .execute()
        )
        return {
            row["key"]: orjson.loads(row["value"])
            for row in (result.data or [])
        }

    def forget(self, namespace: str, key: str) -> None:
        """Remove a fact from long-term memory."""
        self.supabase.table("agent_long_term_memory").delete().eq(
            "namespace", namespace
        ).eq("key", key).execute()

    # =========================================================================
    # UTILITY
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        stats = {}
        for table in [
            "agent_sessions",
            "analysis_history",
            "geological_knowledge",
            "mineral_patterns",
            "learned_workflows",
            "agent_long_term_memory",
        ]:
            result = self.supabase.table(table).select("count", count="exact").execute()
            stats[table] = result.count if hasattr(result, "count") else len(result.data or [])

        # Active sessions
        active = (
            self.supabase.table("agent_sessions")
            .select("count", count="exact")
            .eq("status", "active")
            .execute()
        )
        stats["active_sessions"] = active.count if hasattr(active, "count") else 0

        return stats

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of expired sessions."""
        result = self.supabase.rpc("expire_old_sessions").execute()
        return result.data if result.data else 0
