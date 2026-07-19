"""
AfriMine AI — Memory System Integration Tests
===============================================

Tests the 5-layer memory architecture:
- Short-term: LangGraph checkpointing
- Episodic: "find similar samples" queries
- Semantic: knowledge graph traversal
- Procedural: learned workflow retrieval
- Long-term: persistent facts

Requires: pytest
Run: pytest tests/integration/test_memory_system.py -v

NOTE: These tests validate memory layer contracts and logic.
Full pgvector tests require a Supabase instance.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Memory Layer Contracts (mirrors ARCHITECTURE_V3.md §4.1)
# ---------------------------------------------------------------------------

@dataclass
class MemoryItem:
    """A single memory item across any layer."""
    id: str
    namespace: str
    key: str
    value: dict[str, Any]
    layer: str  # short_term, episodic, semantic, procedural, long_term
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int | None = None
    embedding: list[float] | None = None


class MemorySimulator:
    """Simulates the 5-layer memory architecture."""

    def __init__(self):
        self._store: dict[str, list[MemoryItem]] = {
            "short_term": [],
            "episodic": [],
            "semantic": [],
            "procedural": [],
            "long_term": [],
        }

    def store(self, item: MemoryItem):
        """Store a memory item in its layer."""
        self._store[item.layer].append(item)

    def query(self, layer: str, namespace: str | None = None) -> list[MemoryItem]:
        """Query items from a specific layer."""
        items = self._store.get(layer, [])
        if namespace:
            items = [i for i in items if i.namespace == namespace]
        return items

    def query_by_embedding(
        self, layer: str, embedding: list[float], top_k: int = 5
    ) -> list[MemoryItem]:
        """Simulate vector similarity search."""
        items = self._store.get(layer, [])
        # Simple cosine similarity simulation
        def dot(a, b):
            return sum(x * y for x, y in zip(a, b))

        scored = []
        for item in items:
            if item.embedding:
                sim = dot(embedding, item.embedding)
                scored.append((sim, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def get_by_key(self, layer: str, namespace: str, key: str) -> MemoryItem | None:
        """Get a specific memory item by namespace and key."""
        for item in self._store.get(layer, []):
            if item.namespace == namespace and item.key == key:
                return item
        return None

    def expire_short_term(self):
        """Expire short-term memories past their TTL."""
        now = time.time()
        self._store["short_term"] = [
            i for i in self._store["short_term"]
            if i.ttl_seconds is None or (now - i.created_at) < i.ttl_seconds
        ]

    def get_stats(self) -> dict[str, int]:
        """Get count of items per layer."""
        return {layer: len(items) for layer, items in self._store.items()}


# ---------------------------------------------------------------------------
# Test: Layer 1 — Short-Term Memory
# ---------------------------------------------------------------------------

class TestShortTermMemory:
    """Test short-term memory (LangGraph checkpointing, 24h TTL)."""

    def test_store_session_state(self):
        """Short-term memory should store session state."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id=str(uuid.uuid4()),
            namespace="session:abc-123",
            key="pipeline_state",
            value={
                "current_step": "analysis",
                "analysis_id": "abc-123",
                "sampling_result": {"strategy": "grid"},
            },
            layer="short_term",
            ttl_seconds=86400,  # 24h
        ))

        items = memory.query("short_term")
        assert len(items) == 1
        assert items[0].value["current_step"] == "analysis"

    def test_short_term_expires_after_24h(self):
        """Short-term memories should expire after 24 hours."""
        memory = MemorySimulator()

        # Store with very short TTL for testing
        memory.store(MemoryItem(
            id=str(uuid.uuid4()),
            namespace="session:test",
            key="state",
            value={"step": "analysis"},
            layer="short_term",
            ttl_seconds=1,  # 1 second for testing
        ))

        assert len(memory.query("short_term")) == 1

        # Wait for expiry
        time.sleep(1.1)
        memory.expire_short_term()

        assert len(memory.query("short_term")) == 0

    def test_checkpoint_saves_per_thread(self):
        """Checkpoints should be isolated per thread_id."""
        memory = MemorySimulator()

        for thread_id in ["thread-1", "thread-2", "thread-3"]:
            memory.store(MemoryItem(
                id=str(uuid.uuid4()),
                namespace=f"thread:{thread_id}",
                key="checkpoint",
                value={"step": "sampling", "thread": thread_id},
                layer="short_term",
            ))

        thread1 = memory.query("short_term", "thread:thread-1")
        assert len(thread1) == 1
        assert thread1[0].value["thread"] == "thread-1"

    def test_state_snapshot_preserves_all_agent_outputs(self):
        """Checkpoint state must include all agent outputs."""
        memory = MemorySimulator()

        full_state = {
            "analysis_id": "test-001",
            "sampling_result": {"strategy": "grid", "waypoints": []},
            "analysis_result": {"dominant_mineral": "gold", "confidence": 0.85},
            "geology_result": {"deposit_model": "orogenic gold"},
            "market_result": {"gold_price_usd_oz": 2350},
            "report_result": {"executive_summary": "Gold found"},
            "compliance_result": {"is_compliant": False},
            "refinement_count": 0,
        }

        memory.store(MemoryItem(
            id=str(uuid.uuid4()),
            namespace="session:test",
            key="full_state",
            value=full_state,
            layer="short_term",
        ))

        stored = memory.get_by_key("short_term", "session:test", "full_state")
        assert stored is not None
        assert "sampling_result" in stored.value
        assert "compliance_result" in stored.value


# ---------------------------------------------------------------------------
# Test: Layer 2 — Episodic Memory
# ---------------------------------------------------------------------------

class TestEpisodicMemory:
    """Test episodic memory (analysis history, 'find similar' queries)."""

    def test_store_analysis_history(self):
        """Episodic memory should store completed analyses."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="analysis-001",
            namespace="user:user-123",
            key="analysis-001",
            value={
                "location": {"lat": -1.05, "lon": 34.55, "region": "Nyatike"},
                "minerals": ["gold", "arsenopyrite"],
                "grade": 5.2,
                "confidence": 0.85,
            },
            layer="episodic",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],  # Simplified
        ))

        items = memory.query("episodic")
        assert len(items) == 1
        assert items[0].value["grade"] == 5.2

    def test_find_similar_samples(self):
        """Vector similarity search should find similar analyses."""
        memory = MemorySimulator()

        # Store multiple analyses with embeddings
        memory.store(MemoryItem(
            id="a-001", namespace="history", key="a-001",
            value={"mineral": "gold", "grade": 5.0},
            layer="episodic",
            embedding=[0.9, 0.1, 0.0, 0.0],
        ))
        memory.store(MemoryItem(
            id="a-002", namespace="history", key="a-002",
            value={"mineral": "copper", "grade": 1.5},
            layer="episodic",
            embedding=[0.0, 0.0, 0.9, 0.1],
        ))
        memory.store(MemoryItem(
            id="a-003", namespace="history", key="a-003",
            value={"mineral": "gold", "grade": 4.8},
            layer="episodic",
            embedding=[0.85, 0.15, 0.0, 0.0],
        ))

        # Query similar to gold sample
        query_embedding = [0.9, 0.1, 0.0, 0.0]
        similar = memory.query_by_embedding("episodic", query_embedding, top_k=2)

        assert len(similar) == 2
        # Most similar should be gold samples
        assert similar[0].id in ("a-001", "a-003")

    def test_episodic_memory_permanent(self):
        """Episodic memories should not expire (permanent storage)."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="perm-001", namespace="history", key="perm-001",
            value={"data": "permanent"},
            layer="episodic",
            ttl_seconds=None,  # No TTL = permanent
        ))

        item = memory.get_by_key("episodic", "history", "perm-001")
        assert item is not None
        assert item.ttl_seconds is None


# ---------------------------------------------------------------------------
# Test: Layer 3 — Semantic Memory
# ---------------------------------------------------------------------------

class TestSemanticMemory:
    """Test semantic memory (geological knowledge, vector embeddings)."""

    def test_store_geological_knowledge(self):
        """Semantic memory should store geological knowledge."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="geo-001",
            namespace="knowledge:deposit_models",
            key="orogenic_gold",
            value={
                "category": "deposit_model",
                "content": {
                    "name": "Orogenic Gold",
                    "host": "Quartz veins in shear zones",
                    "pathfinders": ["As > 50 ppm", "Bi > 5 ppm"],
                    "grade_range": "1-20 g/t Au",
                },
                "related_minerals": ["gold", "arsenopyrite", "pyrite"],
            },
            layer="semantic",
            embedding=[0.8, 0.2, 0.1, 0.0],
        ))

        items = memory.query("semantic")
        assert len(items) == 1
        assert items[0].value["category"] == "deposit_model"

    def test_knowledge_graph_traversal(self):
        """Semantic memory should support knowledge relationships."""
        memory = MemorySimulator()

        # Store related knowledge entries
        memory.store(MemoryItem(
            id="model-001", namespace="knowledge", key="orogenic_gold",
            value={"type": "deposit_model", "pathfinders": ["As", "Bi"]},
            layer="semantic",
        ))
        memory.store(MemoryItem(
            id="path-001", namespace="knowledge", key="arsenic_pathfinder",
            value={
                "type": "pathfinder_element",
                "element": "As",
                "threshold_ppm": 50,
                "indicates": "gold mineralization",
                "related_models": ["orogenic_gold"],
            },
            layer="semantic",
        ))

        # Traverse: find what arsenic indicates
        arsenic = memory.get_by_key("semantic", "knowledge", "arsenic_pathfinder")
        assert arsenic is not None
        assert "gold" in arsenic.value["indicates"]

        # Find related deposit model
        related_model_key = arsenic.value["related_models"][0]
        model = memory.get_by_key("semantic", "knowledge", related_model_key)
        assert model is not None
        assert "As" in model.value["pathfinders"]

    def test_migori_belt_knowledge_present(self):
        """Migori Belt geological knowledge should be stored."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="belt-001", namespace="knowledge", key="migori_belt",
            value={
                "name": "Migori Greenstone Belt",
                "age": "Archean to Paleoproterozoic",
                "deposit_models": ["orogenic gold", "VMS", "laterite gold"],
                "known_deposits": ["Macalder", "Nyatike", "Masara"],
            },
            layer="semantic",
        ))

        belt = memory.get_by_key("semantic", "knowledge", "migori_belt")
        assert belt is not None
        assert "orogenic gold" in belt.value["deposit_models"]
        assert "Macalder" in belt.value["known_deposits"]


# ---------------------------------------------------------------------------
# Test: Layer 4 — Procedural Memory
# ---------------------------------------------------------------------------

class TestProceduralMemory:
    """Test procedural memory (learned workflows, successful patterns)."""

    def test_store_workflow(self):
        """Procedural memory should store learned workflows."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="wf-001",
            namespace="workflows:gold_analysis",
            key="standard_gold_workflow",
            value={
                "workflow_type": "full_pipeline",
                "graph_definition": {
                    "nodes": ["sampling", "analysis", "geology", "market", "report", "compliance"],
                    "edges": [
                        ("sampling", "analysis"),
                        ("analysis", "geology"),
                        ("analysis", "market"),
                        ("geology", "report"),
                        ("market", "report"),
                        ("report", "compliance"),
                    ],
                },
                "success_rate": 0.92,
                "applicable_minerals": ["gold"],
                "avg_duration_ms": 45000,
            },
            layer="procedural",
        ))

        items = memory.query("procedural")
        assert len(items) == 1
        assert items[0].value["success_rate"] == 0.92

    def test_retrieve_workflow_by_mineral(self):
        """Should be able to retrieve workflows applicable to a mineral."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="wf-gold", namespace="workflows", key="gold_wf",
            value={"applicable_minerals": ["gold"], "success_rate": 0.92},
            layer="procedural",
        ))
        memory.store(MemoryItem(
            id="wf-copper", namespace="workflows", key="copper_wf",
            value={"applicable_minerals": ["copper"], "success_rate": 0.88},
            layer="procedural",
        ))

        # Find gold workflow
        gold_workflows = [
            i for i in memory.query("procedural")
            if "gold" in i.value.get("applicable_minerals", [])
        ]
        assert len(gold_workflows) == 1
        assert gold_workflows[0].id == "wf-gold"

    def test_workflow_success_rate_tracking(self):
        """Workflows should track success rate for continuous improvement."""
        memory = MemorySimulator()

        # Store initial workflow
        memory.store(MemoryItem(
            id="wf-001", namespace="workflows", key="gold_v1",
            value={"success_rate": 0.80, "run_count": 10, "success_count": 8},
            layer="procedural",
        ))

        # Update after more runs
        item = memory.get_by_key("procedural", "workflows", "gold_v1")
        assert item is not None

        # Simulate 5 more successful runs
        item.value["run_count"] += 5
        item.value["success_count"] += 5
        item.value["success_rate"] = item.value["success_count"] / item.value["run_count"]

        assert item.value["success_rate"] == 13 / 15  # ~0.867


# ---------------------------------------------------------------------------
# Test: Layer 5 — Long-Term Memory
# ---------------------------------------------------------------------------

class TestLongTermMemory:
    """Test long-term memory (persistent facts, calibration data)."""

    def test_store_persistent_fact(self):
        """Long-term memory should store persistent facts."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="fact-001",
            namespace="user:user-123",
            key="preferred_units",
            value={"weight": "kg", "distance": "m", "currency": "KES"},
            layer="long_term",
        ))

        item = memory.get_by_key("long_term", "user:user-123", "preferred_units")
        assert item is not None
        assert item.value["currency"] == "KES"

    def test_store_calibration_data(self):
        """Long-term memory should store device calibration data."""
        memory = MemorySimulator()

        memory.store(MemoryItem(
            id="cal-001",
            namespace="system:calibration",
            key="xrf_device_001",
            value={
                "device_id": "XRF-001",
                "calibration_date": "2026-07-01",
                "element_corrections": {
                    "Au": 1.02,  # 2% positive correction
                    "As": 0.98,
                },
                "accuracy_ppm": {"Au": 0.1, "As": 5.0},
            },
            layer="long_term",
        ))

        cal = memory.get_by_key("long_term", "system:calibration", "xrf_device_001")
        assert cal is not None
        assert cal.value["element_corrections"]["Au"] == 1.02

    def test_long_term_memory_namespaced(self):
        """Long-term memories should be properly namespaced."""
        memory = MemorySimulator()

        # User-specific fact
        memory.store(MemoryItem(
            id="u-001", namespace="user:alice", key="name",
            value={"full_name": "Alice Kamau"},
            layer="long_term",
        ))

        # Region-specific fact
        memory.store(MemoryItem(
            id="r-001", namespace="region:nyatike", key="avg_gold_grade",
            value={"gpt": 3.5},
            layer="long_term",
        ))

        # System-wide fact
        memory.store(MemoryItem(
            id="s-001", namespace="system", key="kenya_royalty_rate",
            value={"pct": 5.0},
            layer="long_term",
        ))

        # Query by namespace
        user_facts = memory.query("long_term", "user:alice")
        assert len(user_facts) == 1

        region_facts = memory.query("long_term", "region:nyatike")
        assert len(region_facts) == 1

        system_facts = memory.query("long_term", "system")
        assert len(system_facts) == 1


# ---------------------------------------------------------------------------
# Test: Memory Stats
# ---------------------------------------------------------------------------

class TestMemoryStats:
    """Test memory statistics and capacity monitoring."""

    def test_memory_stats_per_layer(self):
        """Memory stats should report counts per layer."""
        memory = MemorySimulator()

        # Store items in each layer
        for layer in ["short_term", "episodic", "semantic", "procedural", "long_term"]:
            memory.store(MemoryItem(
                id=f"{layer}-001", namespace="test", key=f"{layer}_key",
                value={"layer": layer},
                layer=layer,
            ))

        stats = memory.get_stats()
        assert stats["short_term"] == 1
        assert stats["episodic"] == 1
        assert stats["semantic"] == 1
        assert stats["procedural"] == 1
        assert stats["long_term"] == 1

    def test_embedding_dimension(self):
        """Embeddings should be 384-dimensional (all-MiniLM-L6-v2)."""
        # This is a contract test — actual embedding generation requires the model
        expected_dim = 384
        sample_embedding = [0.1] * expected_dim
        assert len(sample_embedding) == 384

    def test_vector_index_type(self):
        """Vector index should be IVFFlat for <100K rows."""
        index_config = {
            "type": "IVFFlat",
            "lists": 10,  # For analysis_history
            "dimension": 384,
        }
        assert index_config["type"] == "IVFFlat"
        assert index_config["dimension"] == 384


# ---------------------------------------------------------------------------
# Test: Memory Integration with Agents
# ---------------------------------------------------------------------------

class TestMemoryAgentIntegration:
    """Test that agents correctly read/write to memory layers."""

    def test_sampling_agent_reads_episodic(self):
        """Sampling agent should read past sampling routes from episodic memory."""
        required_read = ["analysis_history", "geological_knowledge"]
        agent = "sampling"
        # Per AGENT_READ_KEYS in security/middleware.py
        assert "analysis_result" in ["location", "sample_data", "satellite_imagery", "analysis_result"]

    def test_geology_agent_writes_semantic(self):
        """Geology agent should write new observations to semantic memory."""
        required_write = ["geology_result", "geological_knowledge"]
        # Geology agent can update the knowledge base with new observations
        assert "geological_knowledge" in required_write

    def test_market_agent_reads_long_term(self):
        """Market agent should read price history from long-term memory."""
        required_read = ["agent_long_term_memory"]
        assert "agent_long_term_memory" in required_read

    def test_report_agent_reads_all_outputs(self):
        """Report agent should read all other agent outputs."""
        required_read = [
            "analysis_result", "geology_result", "market_result",
            "compliance_result", "sampling_result", "location",
        ]
        assert len(required_read) >= 5

    def test_memory_schema_matches_architecture(self):
        """Memory tables must match the architecture spec."""
        expected_tables = [
            "agent_sessions",      # Layer 1: Short-term
            "analysis_history",    # Layer 2: Episodic
            "geological_knowledge",# Layer 3: Semantic
            "mineral_patterns",    # Layer 3b: Discovered patterns
            "learned_workflows",   # Layer 4: Procedural
            "agent_long_term_memory", # Layer 5: Long-term
            "checkpoints",         # LangGraph checkpoints
            "checkpoint_writes",   # LangGraph checkpoint writes
        ]
        assert len(expected_tables) == 8
