"""
AfriMine AI — Geological Knowledge Graph

Manages structured geological knowledge: deposit models, pathfinder elements,
alteration signatures, tectonic settings, and their relationships.

Uses NetworkX for in-memory graph operations and Supabase for persistence.
Enables:
- "What pathfinder elements correlate with gold in the Migori Belt?"
- "What deposit models are compatible with sericite + quartz alteration?"
- "What's the typical grade range for orogenic gold in greenstone belts?"

Usage:
    kg = GeologicalKnowledgeGraph()

    # Query knowledge
    results = kg.search("pathfinder elements for gold", category="pathfinder_element")

    # Add knowledge
    kg.add(
        category="pathfinder_element",
        title="Arsenic as gold pathfinder in Migori Belt",
        description="As > 50 ppm strongly correlates with Au mineralization",
        content={"element": "As", "threshold_ppm": 50, "correlates_with": "Au"},
        related_minerals=["gold"],
    )

    # Get deposit model
    model = kg.get_deposit_model("orogenic_gold")

    # Find related knowledge
    related = kg.get_related("knowledge-id-here")
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Any, Optional
from datetime import datetime, timezone

import orjson
import networkx as nx

logger = logging.getLogger("afrimine.knowledge_graph")


class GeologicalKnowledgeGraph:
    """
    Geological knowledge graph backed by Supabase + NetworkX.

    Supabase: persistent storage with vector embeddings for semantic search.
    NetworkX: in-memory graph for relationship traversal.
    """

    # =========================================================================
    # Pre-loaded geological knowledge for the Migori Belt / Kenya
    # =========================================================================

    SEED_KNOWLEDGE = [
        # --- Deposit Models ---
        {
            "category": "deposit_model",
            "title": "Orogenic Gold — Migori Belt",
            "description": (
                "Gold mineralization in the Migori Belt is orogenic type, hosted in "
                "NE-trending shear zones within Archean greenstone assemblages. "
                "Ore is associated with quartz veins, pyrite, and arsenopyrite. "
                "Typical grades: 1-15 g/t Au, with bonanza shoots up to 50+ g/t."
            ),
            "content": {
                "model_name": "orogenic_gold",
                "host_rocks": ["greenstone", "schist", "banded_iron_formation"],
                "structural_control": "shear_zones_NE_trending",
                "alteration": ["sericite", "quartz", "carbonate", "chlorite"],
                "sulfide_minerals": ["pyrite", "arsenopyrite", "chalcopyrite"],
                "typical_grade_range_gpt": [1.0, 15.0],
                "bonanza_grade_gpt": 50.0,
                "depth_extent_m": [50, 500],
                "deposit_size_range_tonnes": [10000, 5000000],
            },
            "related_minerals": ["gold", "silver"],
            "related_regions": ["migori_belt", "nyatike", "kenya"],
            "source": "USGS, Kenya Geological Survey",
        },
        {
            "category": "deposit_model",
            "title": "VMS (Volcanogenic Massive Sulfide)",
            "description": (
                "VMS deposits form at or near the seafloor from hydrothermal vents. "
                "In the Migori Belt, VMS-style Cu-Zn-Au mineralization occurs in "
                "mafic-felsic volcanic sequences. Characterized by massive sulfide "
                "lenses with stockwork veins below."
            ),
            "content": {
                "model_name": "vms",
                "host_rocks": ["mafic_volcanics", "felsic_volcanics", "chert"],
                "structural_control": "stratiform_lens",
                "alteration": ["chlorite", "sericite", "silicification"],
                "sulfide_minerals": ["pyrite", "pyrrhotite", "chalcopyrite", "sphalerite"],
                "typical_grade_range_pct": {"cu": [0.5, 3.0], "zn": [1.0, 10.0]},
                "typical_grade_range_gpt": {"au": [0.5, 5.0]},
            },
            "related_minerals": ["copper", "zinc", "gold", "silver"],
            "related_regions": ["migori_belt", "kenya"],
            "source": "USGS Mineral Deposit Models",
        },

        # --- Pathfinder Elements ---
        {
            "category": "pathfinder_element",
            "title": "Arsenic → Gold Pathfinder (Migori Belt)",
            "description": (
                "Arsenic (As) is the strongest pathfinder for gold in the Migori Belt. "
                "As > 50 ppm in soil or rock samples indicates potential gold mineralization. "
                "As/Au ratio of 1000:1 to 5000:1 is typical in orogenic gold deposits."
            ),
            "content": {
                "pathfinder": "As",
                "target": "Au",
                "threshold_ppm": 50,
                "strong_signal_ppm": 200,
                "typical_ratio": "1000:1 to 5000:1",
                "confidence": 0.85,
                "mechanism": "As substitutes in arsenopyrite which co-precipitates with Au",
            },
            "related_minerals": ["gold", "arsenic"],
            "related_regions": ["migori_belt", "kenya"],
            "source": "Geochemical surveys, Migori County",
        },
        {
            "category": "pathfinder_element",
            "title": "Copper → Gold Association (VMS)",
            "description": (
                "Copper enrichment (Cu > 500 ppm) can indicate VMS-style gold "
                "mineralization. Cu:Au ratio helps distinguish VMS from orogenic gold."
            ),
            "content": {
                "pathfinder": "Cu",
                "target": "Au",
                "threshold_ppm": 500,
                "association_type": "VMS",
                "confidence": 0.70,
            },
            "related_minerals": ["gold", "copper"],
            "related_regions": ["migori_belt"],
            "source": "Geochemical surveys",
        },
        {
            "category": "pathfinder_element",
            "title": "Antimony → Gold Pathfinder",
            "description": (
                "Antimony (Sb) is a secondary pathfinder for orogenic gold. "
                "Sb > 10 ppm in soil is anomalous. Sb often forms stibnite (Sb2S3) "
                "in the same structural conduits as gold."
            ),
            "content": {
                "pathfinder": "Sb",
                "target": "Au",
                "threshold_ppm": 10,
                "confidence": 0.65,
            },
            "related_minerals": ["gold", "antimony"],
            "related_regions": ["migori_belt"],
            "source": "Geochemical literature",
        },

        # --- Alteration Signatures ---
        {
            "category": "alteration_signature",
            "title": "Sericite-Quartz Alteration (Gold Indicator)",
            "description": (
                "Sericite (fine-grained muscovite) + quartz alteration is the hallmark "
                "of orogenic gold systems. Visible as white/gray bleached zones adjacent "
                "to quartz veins. Sentinel-2 band ratio B4/B2 can detect this alteration."
            ),
            "content": {
                "alteration_type": "sericite_quartz",
                "minerals": ["sericite", "quartz", "pyrite"],
                "indicates": "orogenic_gold",
                "sentinel2_ratios": {"B4_B2": ">1.5", "B11_B12": "<1.0"},
                "field_signature": "white_bleached_rock_adjacent_to_quartz_veins",
                "confidence": 0.80,
            },
            "related_minerals": ["gold"],
            "related_regions": ["migori_belt"],
            "source": "Remote sensing studies, Kenya",
        },
        {
            "category": "alteration_signature",
            "title": "Iron Oxide Staining (Gossan)",
            "description": (
                "Red/brown iron oxide staining on rock surfaces indicates oxidation of "
                "sulfide minerals — a gossan. Gossans are surface expressions of "
                "subsurface sulfide mineralization. Goethite and hematite are key minerals."
            ),
            "content": {
                "alteration_type": "iron_oxide_gossan",
                "minerals": ["goethite", "hematite", "limonite"],
                "indicates": "subsurface_sulfide",
                "field_signature": "red_brown_stained_rock",
                "sentinel2_ratios": {"B4_B3": ">1.2"},
                "confidence": 0.70,
            },
            "related_minerals": ["gold", "copper", "iron"],
            "related_regions": ["migori_belt"],
            "source": "Field observations",
        },

        # --- Mineral Associations ---
        {
            "category": "mineral_association",
            "title": "Pyrite-Arsenopyrite-Gold Association",
            "description": (
                "The pyrite + arsenopyrite + gold assemblage is diagnostic of orogenic "
                "gold deposits. Gold occurs as inclusions in pyrite and along grain "
                "boundaries of arsenopyrite. Visible gold is rare; most is sub-microscopic."
            ),
            "content": {
                "minerals": ["pyrite", "arsenopyrite", "gold"],
                "association_type": "orogenic_gold_diagnostic",
                "gold_occurrence": "inclusions_in_pyrite_and_arsenopyrite",
                "typical_grain_size_um": [1, 100],
                "confidence": 0.90,
            },
            "related_minerals": ["gold", "pyrite", "arsenopyrite"],
            "related_regions": ["migori_belt"],
            "source": "Ore microscopy studies",
        },

        # --- Grade Thresholds ---
        {
            "category": "grade_threshold",
            "title": "Kenya Gold Economic Cut-off Grade",
            "description": (
                "The economic cut-off grade for gold mining in Kenya depends on the "
                "mining method. For artisanal/small-scale: ~0.5 g/t Au. For small "
                "open-pit: ~1.0 g/t Au. For underground: ~3.0 g/t Au. These assume "
                "gold price of ~$2,300/oz and local operating costs."
            ),
            "content": {
                "mineral": "gold",
                "cut_off_grades": {
                    "artisanal_gpt": 0.5,
                    "small_open_pit_gpt": 1.0,
                    "underground_gpt": 3.0,
                },
                "assumes_gold_price_usd_oz": 2300,
                "currency": "KES",
                "confidence": 0.75,
            },
            "related_minerals": ["gold"],
            "related_regions": ["kenya"],
            "source": "Kenya Mining Act 2016, industry estimates",
        },

        # --- Tectonic Settings ---
        {
            "category": "tectonic_setting",
            "title": "Migori Greenstone Belt",
            "description": (
                "The Migori Belt is an Archean greenstone belt in southwestern Kenya, "
                "part of the Tanzania Craton margin. It consists of metavolcanics and "
                "metasediments with NE-trending shear zones. The belt hosts orogenic "
                "gold, VMS Cu-Zn, and laterite-type mineralization."
            ),
            "content": {
                "belt_name": "migori_greenstone_belt",
                "age_ga": [2.7, 2.8],
                "lithology": ["metavolcanics", "metasediments", "banded_iron_formation"],
                "structure": "NE_trending_shear_zones",
                "known_deposits": ["migori_gold", "macalder_copper"],
                "area_km2": 500,
            },
            "related_minerals": ["gold", "copper", "zinc"],
            "related_regions": ["migori_belt", "nyatike", "kenya"],
            "source": "Kenya Geological Survey, academic literature",
        },

        # --- Processing Methods ---
        {
            "category": "processing_method",
            "title": "Gravity Separation for Alluvial Gold",
            "description": (
                "Alluvial gold in the Migori Belt can be recovered by gravity separation "
                "(sluice boxes, shaking tables). Recovery rates: 60-70% for coarse gold "
                "(>100 mesh), <30% for fine gold (<200 mesh). Mercury-free methods "
                "recommended."
            ),
            "content": {
                "method": "gravity_separation",
                "suitable_for": "alluvial_gold",
                "recovery_rate_coarse_pct": [60, 70],
                "recovery_rate_fine_pct": [10, 30],
                "equipment": ["sluice_box", "shaking_table", "centrifugal_concentrator"],
                "environmental_note": "mercury_free_recommended",
            },
            "related_minerals": ["gold"],
            "related_regions": ["migori_belt"],
            "source": "ASM best practices, UNEP",
        },
    ]

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
        self._graph: nx.DiGraph | None = None

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
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        category: str | None = None,
        n: int = 5,
    ) -> list[dict]:
        """
        Search the geological knowledge base.

        Uses vector similarity via pgvector, optionally filtered by category.
        """
        results = self.vector_store.search_knowledge(
            query=query,
            top_k=n,
            category=category,
        )

        # Enrich with full content
        for r in results:
            kid = r.get("knowledge_id")
            if kid:
                full = self.get(kid)
                if full:
                    r["content"] = full.get("content")
                    r["related_minerals"] = full.get("related_minerals")
                    r["related_regions"] = full.get("related_regions")

        return results

    def get(self, knowledge_id: str) -> dict | None:
        """Get a knowledge entry by ID."""
        result = (
            self.client.table("geological_knowledge")
            .select("*")
            .eq("knowledge_id", knowledge_id)
            .single()
            .execute()
        )
        if not result.data:
            return None

        row = result.data
        # Update reference tracking
        self.client.table("geological_knowledge").update({
            "times_referenced": (row.get("times_referenced") or 0) + 1,
            "last_referenced": datetime.now(timezone.utc).isoformat(),
        }).eq("knowledge_id", knowledge_id).execute()

        row.pop("embedding", None)
        return row

    # -------------------------------------------------------------------------
    # Add Knowledge
    # -------------------------------------------------------------------------

    def add(
        self,
        category: str,
        title: str,
        description: str,
        content: dict,
        related_minerals: list[str] | None = None,
        related_regions: list[str] | None = None,
        related_deposit_models: list[str] | None = None,
        source: str | None = None,
        source_url: str | None = None,
        confidence: float = 0.8,
        verified: bool = False,
    ) -> str:
        """Add a knowledge entry to the geological knowledge base."""
        knowledge_id = str(uuid.uuid4())

        row = {
            "knowledge_id": knowledge_id,
            "category": category,
            "title": title,
            "description": description,
            "content": orjson.dumps(content).decode(),
            "related_minerals": related_minerals or [],
            "related_regions": related_regions or [],
            "related_deposit_models": related_deposit_models or [],
            "source": source,
            "source_url": source_url,
            "confidence": confidence,
            "verified": verified,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.client.table("geological_knowledge").insert(row).execute()

        # Generate embedding
        embedding_text = f"{title}. {description}"
        try:
            embedding = self.vector_store.embed(embedding_text)
            self.client.table("geological_knowledge").update({
                "embedding": embedding,
            }).eq("knowledge_id", knowledge_id).execute()
        except Exception as e:
            logger.warning("Failed to embed knowledge %s: %s", knowledge_id, e)

        logger.info("Added knowledge: %s (%s) [%s]", title[:50], knowledge_id, category)
        return knowledge_id

    def seed_knowledge(self) -> int:
        """
        Seed the knowledge base with initial geological data for the Migori Belt.
        Run once during setup. Returns count of entries added.
        """
        count = 0
        for entry in self.SEED_KNOWLEDGE:
            # Check if already exists (by title)
            existing = (
                self.client.table("geological_knowledge")
                .select("knowledge_id")
                .eq("title", entry["title"])
                .execute()
            )
            if existing.data:
                logger.debug("Knowledge already exists: %s", entry["title"][:50])
                continue

            self.add(**entry)
            count += 1

        logger.info("Seeded %d geological knowledge entries", count)
        return count

    # -------------------------------------------------------------------------
    # Deposit Models
    # -------------------------------------------------------------------------

    def get_deposit_model(self, model_name: str) -> dict | None:
        """Get a specific deposit model by name."""
        result = (
            self.client.table("geological_knowledge")
            .select("*")
            .eq("category", "deposit_model")
            .execute()
        )

        for row in (result.data or []):
            content = row.get("content", {})
            if isinstance(content, str):
                content = orjson.loads(content)
            if content.get("model_name") == model_name:
                row.pop("embedding", None)
                return row

        return None

    def get_pathfinders(self, target_mineral: str) -> list[dict]:
        """Get all pathfinder elements for a target mineral."""
        result = (
            self.client.table("geological_knowledge")
            .select("*")
            .eq("category", "pathfinder_element")
            .execute()
        )

        pathfinders = []
        for row in (result.data or []):
            content = row.get("content", {})
            if isinstance(content, str):
                content = orjson.loads(content)
            if content.get("target") == target_mineral:
                row.pop("embedding", None)
                pathfinders.append(row)

        return pathfinders

    def get_alteration_signatures(self, deposit_model: str | None = None) -> list[dict]:
        """Get alteration signatures, optionally filtered by deposit model."""
        result = (
            self.client.table("geological_knowledge")
            .select("*")
            .eq("category", "alteration_signature")
            .execute()
        )

        signatures = []
        for row in (result.data or []):
            content = row.get("content", {})
            if isinstance(content, str):
                content = orjson.loads(content)
            if deposit_model and content.get("indicates") != deposit_model:
                continue
            row.pop("embedding", None)
            signatures.append(row)

        return signatures

    # -------------------------------------------------------------------------
    # Pattern Discovery
    # -------------------------------------------------------------------------

    def discover_patterns(
        self,
        mineral: str | None = None,
        region: str | None = None,
        min_support: int = 3,
    ) -> list[dict]:
        """
        Discover patterns across analyses.

        Finds element correlations, grade distributions, and spatial clusters
        that appear repeatedly in the analysis history.
        """
        # Query analyses
        query = (
            self.client.table("analysis_history")
            .select(
                "analysis_id, mineral_type, detected_minerals, estimated_grade, "
                "confidence_score, location, analysis_output, geology_output"
            )
            .eq("validation_status", "validated")
        )

        if mineral:
            query = query.eq("mineral_type", mineral)
        if region:
            query = query.eq("location->>'region'", region)

        result = query.limit(500).execute()
        analyses = result.data or []

        if len(analyses) < min_support:
            return []

        patterns = []

        # --- Element Correlation Pattern ---
        if mineral:
            # Check which pathfinder elements appear consistently
            pathfinder_counts: dict[str, int] = {}
            for a in analyses:
                geo = a.get("geology_output", {})
                if isinstance(geo, str):
                    geo = orjson.loads(geo)
                pathfinders = geo.get("pathfinder_elements", [])
                for pf in pathfinders:
                    pathfinder_counts[pf] = pathfinder_counts.get(pf, 0) + 1

            for element, count in pathfinder_counts.items():
                if count >= min_support:
                    confidence = count / len(analyses)
                    patterns.append({
                        "pattern_type": "element_correlation",
                        "name": f"{element} → {mineral} correlation",
                        "description": f"{element} appears in {count}/{len(analyses)} validated {mineral} analyses",
                        "conditions": {
                            "pathfinder": element,
                            "target": mineral,
                            "support": count,
                            "total": len(analyses),
                        },
                        "confidence": round(confidence, 3),
                        "support_count": count,
                    })

        # --- Grade Distribution Pattern ---
        grades = [
            a["estimated_grade"] for a in analyses
            if a.get("estimated_grade") is not None
        ]
        if len(grades) >= min_support:
            import numpy as np
            arr = np.array(grades, dtype=float)
            patterns.append({
                "pattern_type": "grade_distribution",
                "name": f"Grade distribution for {mineral or 'all minerals'}",
                "description": f"Mean grade: {np.mean(arr):.2f}, std: {np.std(arr):.2f}, n={len(grades)}",
                "conditions": {
                    "mean": round(float(np.mean(arr)), 3),
                    "std": round(float(np.std(arr)), 3),
                    "median": round(float(np.median(arr)), 3),
                    "p25": round(float(np.percentile(arr, 25)), 3),
                    "p75": round(float(np.percentile(arr, 75)), 3),
                    "count": len(grades),
                },
                "confidence": 0.85,
                "support_count": len(grades),
            })

        return patterns

    # -------------------------------------------------------------------------
    # Graph Operations (NetworkX)
    # -------------------------------------------------------------------------

    def build_graph(self) -> nx.DiGraph:
        """
        Build an in-memory NetworkX graph from the knowledge base.
        Nodes: knowledge entries
        Edges: relationships (mineral, region, deposit model)
        """
        if self._graph is not None:
            return self._graph

        result = self.client.table("geological_knowledge").select("*").execute()
        entries = result.data or []

        G = nx.DiGraph()

        # Add nodes
        for entry in entries:
            content = entry.get("content", {})
            if isinstance(content, str):
                content = orjson.loads(content)

            G.add_node(entry["knowledge_id"], **{
                "category": entry["category"],
                "title": entry["title"],
                "minerals": entry.get("related_minerals", []),
                "regions": entry.get("related_regions", []),
                "deposit_models": entry.get("related_deposit_models", []),
            })

        # Add edges based on shared minerals/regions/models
        nodes = list(G.nodes(data=True))
        for i, (id_a, data_a) in enumerate(nodes):
            for id_b, data_b in nodes[i + 1:]:
                shared_minerals = set(data_a.get("minerals", [])) & set(data_b.get("minerals", []))
                shared_regions = set(data_a.get("regions", [])) & set(data_b.get("regions", []))
                shared_models = set(data_a.get("deposit_models", [])) & set(data_b.get("deposit_models", []))

                if shared_minerals or shared_regions or shared_models:
                    weight = len(shared_minerals) + len(shared_regions) + len(shared_models)
                    G.add_edge(id_a, id_b, weight=weight, **{
                        "shared_minerals": list(shared_minerals),
                        "shared_regions": list(shared_regions),
                        "shared_models": list(shared_models),
                    })

        self._graph = G
        logger.info("Built knowledge graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
        return G

    def get_related(self, knowledge_id: str, max_depth: int = 2) -> list[dict]:
        """Find knowledge entries related to the given ID (graph traversal)."""
        G = self.build_graph()

        if knowledge_id not in G:
            return []

        # BFS to find related nodes
        related = []
        visited = {knowledge_id}
        queue = [(knowledge_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            for neighbor in G.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    node_data = G.nodes[neighbor]
                    related.append({
                        "knowledge_id": neighbor,
                        "category": node_data.get("category"),
                        "title": node_data.get("title"),
                        "depth": depth + 1,
                        "edge_data": G.edges[current, neighbor],
                    })
                    queue.append((neighbor, depth + 1))

        # Also check predecessors
        for predecessor in G.predecessors(knowledge_id):
            if predecessor not in visited:
                node_data = G.nodes[predecessor]
                related.append({
                    "knowledge_id": predecessor,
                    "category": node_data.get("category"),
                    "title": node_data.get("title"),
                    "depth": 1,
                    "edge_data": G.edges[predecessor, knowledge_id],
                })

        return related
