"""
AfriMine AI — Geological Vector Store

Manages vector embeddings for geological data using pgvector in Supabase.
Enables semantic similarity search across:
- Mineral analysis descriptions
- Geological knowledge entries
- Analysis history summaries
- Pattern descriptions

Uses all-MiniLM-L6-v2 (384 dimensions) — free, fast, good quality.
Model is downloaded once and cached locally (works offline after first run).

Usage:
    store = GeologicalVectorStore()

    # Embed and store
    store.add("analysis", analysis_id, "Gold-bearing quartz vein in migori greenstone belt")

    # Search
    results = store.search("similar gold deposits in kenya", top_k=5)

    # Batch embed
    embeddings = store.embed_batch(["sample 1 description", "sample 2 description"])
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("afrimine.vector_store")

# Singleton model instance (loaded once, shared across calls)
_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"
_DIMENSION = 384


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("Loaded embedding model: %s (dim=%d)", _MODEL_NAME, _DIMENSION)
    return _model


class GeologicalVectorStore:
    """
    Vector store for geological data using Supabase pgvector.

    Tables with vector columns:
    - analysis_history.embedding
    - geological_knowledge.embedding
    - mineral_patterns.embedding
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY", "")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from supabase import create_client
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    # -------------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Generate a 384-dim embedding for a single text."""
        model = _get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Generate embeddings for multiple texts (batched for efficiency)."""
        if not texts:
            return []
        model = _get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    # -------------------------------------------------------------------------
    # Store Operations
    # -------------------------------------------------------------------------

    def add(
        self,
        table: str,
        entity_id: str,
        text: str,
        id_column: str | None = None,
    ) -> None:
        """
        Generate embedding and store it in the specified table.

        Args:
            table: Supabase table name (e.g., 'analysis_history')
            entity_id: Row ID to update
            text: Text to embed
            id_column: Primary key column name (defaults to '{table singular}_id')
        """
        if id_column is None:
            # Infer ID column: analysis_history -> analysis_id
            singular = table.rstrip("s")
            if singular.endswith("ie"):
                singular = singular[:-2] + "y"
            id_column = f"{singular}_id"

        embedding = self.embed(text)

        self.client.table(table).update({
            "embedding": embedding,
        }).eq(id_column, entity_id).execute()

        logger.debug("Stored embedding for %s/%s (%d dims)", table, entity_id, _DIMENSION)

    def add_batch(
        self,
        table: str,
        ids: list[str],
        texts: list[str],
        id_column: str | None = None,
    ) -> int:
        """
        Batch embed and store multiple rows.

        Returns: number of rows updated.
        """
        if id_column is None:
            singular = table.rstrip("s")
            if singular.endswith("ie"):
                singular = singular[:-2] + "y"
            id_column = f"{singular}_id"

        embeddings = self.embed_batch(texts)
        count = 0

        for entity_id, embedding in zip(ids, embeddings):
            self.client.table(table).update({
                "embedding": embedding,
            }).eq(id_column, entity_id).execute()
            count += 1

        logger.info("Batch stored %d embeddings in %s", count, table)
        return count

    # -------------------------------------------------------------------------
    # Search Operations
    # -------------------------------------------------------------------------

    def search_analyses(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.6,
        mineral_filter: str | None = None,
        region_filter: str | None = None,
    ) -> list[dict]:
        """
        Find analyses similar to the query text.

        Uses the find_similar_analyses SQL function (pgvector cosine distance).
        Returns: list of {analysis_id, similarity, mineral_type, confidence_score, created_at}
        """
        query_embedding = self.embed(query)

        # Use the SQL function defined in memory_schema.sql
        result = self.client.rpc(
            "find_similar_analyses",
            {
                "query_embedding": query_embedding,
                "match_count": top_k,
                "match_threshold": threshold,
                "filter_mineral": mineral_filter,
                "filter_region": region_filter,
            },
        ).execute()

        return result.data or []

    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> list[dict]:
        """
        Find geological knowledge entries similar to the query.

        Returns: list of {knowledge_id, similarity, category, title, description}
        """
        query_embedding = self.embed(query)

        result = self.client.rpc(
            "find_relevant_knowledge",
            {
                "query_embedding": query_embedding,
                "match_count": top_k,
                "filter_category": category,
            },
        ).execute()

        return result.data or []

    def search_patterns(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Find mineral patterns similar to the query.

        Direct pgvector query (no SQL function needed for this table).
        """
        query_embedding = self.embed(query)

        # Manual cosine similarity query
        result = (
            self.client.table("mineral_patterns")
            .select(
                "pattern_id, pattern_type, name, description, "
                "confidence, support_count, applicable_regions, "
                "status, (1 - (embedding <=> $1)) as similarity"
            )
            .gte("1 - (embedding <=> $1)", 0.5)
            .order("embedding <=> $1", desc=False)
            .limit(top_k)
            .execute()
        )

        # Fallback: if the above doesn't work with Supabase client,
        # use raw RPC
        if not result.data:
            result = self.client.rpc(
                "search_patterns",
                {
                    "query_embedding": query_embedding,
                    "match_count": top_k,
                },
            ).execute()

        return result.data or []

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two texts."""
        emb_a = np.array(self.embed(text_a))
        emb_b = np.array(self.embed(text_b))
        return float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))

    def cluster_texts(
        self, texts: list[str], n_clusters: int = 5
    ) -> list[list[int]]:
        """
        Cluster texts by embedding similarity (KMeans).
        Returns: list of clusters, each containing indices into the input list.
        """
        from sklearn.cluster import KMeans

        if len(texts) < n_clusters:
            return [[i] for i in range(len(texts))]

        embeddings = np.array(self.embed_batch(texts))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        clusters: list[list[int]] = [[] for _ in range(n_clusters)]
        for idx, label in enumerate(labels):
            clusters[label].append(idx)

        return clusters

    @staticmethod
    def dimension() -> int:
        """Return the embedding dimension (384 for all-MiniLM-L6-v2)."""
        return _DIMENSION
