"""
AfriMine AI — Checkpointer Integration
========================================

Wraps the Supabase checkpointer for LangGraph state persistence.
Provides factory function and in-memory fallback for testing.

Usage:
    checkpointer = create_checkpointer()
    graph = build_graph(checkpointer=checkpointer)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from config import settings

logger = logging.getLogger("afrimine.checkpoint")


class SupabaseCheckpointer:
    """
    Supabase-backed checkpoint saver for LangGraph.

    Stores checkpoint data in the `langgraph_checkpoints` table.
    Falls back gracefully if Supabase is unavailable.
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        max_checkpoints_per_thread: int = 50,
    ):
        self._max_per_thread = max_checkpoints_per_thread
        self._client = None
        self._table = "langgraph_checkpoints"

        try:
            from supabase import create_client
            self._client = create_client(supabase_url, supabase_key)
            logger.info("Supabase checkpointer initialized (table=%s)", self._table)
        except Exception as e:
            logger.error("Failed to create Supabase client: %s", e)
            raise

    def put(self, config: dict, checkpoint: dict, metadata: dict) -> None:
        """Save a checkpoint to Supabase."""
        if not self._client:
            return

        thread_id = config.get("configurable", {}).get("thread_id", "unknown")
        checkpoint_id = checkpoint.get("id", str(int(time.time() * 1000)))

        try:
            row = {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "checkpoint_json": json.dumps(checkpoint),
                "metadata_json": json.dumps(metadata),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._client.table(self._table).upsert(
                row, on_conflict="thread_id,checkpoint_id"
            ).execute()

            # Prune old checkpoints for this thread
            self._prune(thread_id)

            logger.debug("Checkpoint saved: thread=%s id=%s", thread_id, checkpoint_id)
        except Exception as e:
            logger.warning("Failed to save checkpoint: %s", e)

    def get(self, config: dict) -> dict | None:
        """Retrieve the latest checkpoint for a thread."""
        if not self._client:
            return None

        thread_id = config.get("configurable", {}).get("thread_id", "")
        if not thread_id:
            return None

        try:
            result = (
                self._client.table(self._table)
                .select("checkpoint_json")
                .eq("thread_id", thread_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if result.data:
                return json.loads(result.data[0]["checkpoint_json"])
        except Exception as e:
            logger.warning("Failed to get checkpoint: %s", e)

        return None

    def list(self, config: dict, limit: int = 10) -> list[dict]:
        """List checkpoints for a thread."""
        if not self._client:
            return []

        thread_id = config.get("configurable", {}).get("thread_id", "")
        if not thread_id:
            return []

        try:
            result = (
                self._client.table(self._table)
                .select("checkpoint_id,metadata_json,created_at")
                .eq("thread_id", thread_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return [
                {
                    "id": row["checkpoint_id"],
                    "metadata": json.loads(row.get("metadata_json", "{}")),
                    "created_at": row["created_at"],
                }
                for row in (result.data or [])
            ]
        except Exception as e:
            logger.warning("Failed to list checkpoints: %s", e)
            return []

    def _prune(self, thread_id: str) -> None:
        """Remove old checkpoints beyond the per-thread limit."""
        if not self._client:
            return
        try:
            # Get count
            count_result = (
                self._client.table(self._table)
                .select("checkpoint_id", count="exact")
                .eq("thread_id", thread_id)
                .execute()
            )
            total = count_result.count if hasattr(count_result, "count") else 0
            if total is None:
                total = len(count_result.data or [])

            if total > self._max_per_thread:
                # Delete oldest
                old = (
                    self._client.table(self._table)
                    .select("checkpoint_id")
                    .eq("thread_id", thread_id)
                    .order("created_at", desc=False)
                    .limit(total - self._max_per_thread)
                    .execute()
                )
                for row in (old.data or []):
                    self._client.table(self._table).delete().eq(
                        "checkpoint_id", row["checkpoint_id"]
                    ).execute()
        except Exception as e:
            logger.debug("Checkpoint pruning failed (non-fatal): %s", e)


def create_checkpointer(use_memory: bool = False) -> Any:
    """
    Create a LangGraph checkpointer.

    Args:
        use_memory: If True, use in-memory checkpointer (for testing).
                    If False, use Supabase PostgreSQL (production).

    Returns:
        A checkpoint saver instance compatible with LangGraph.
    """
    if use_memory:
        logger.info("Using in-memory checkpointer (testing mode)")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.warning(
            "Supabase credentials not set — falling back to in-memory checkpointer"
        )
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    logger.info("Creating Supabase checkpointer")
    try:
        checkpointer = SupabaseCheckpointer(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_KEY,
            max_checkpoints_per_thread=settings.MAX_CHECKPOINTS_PER_THREAD,
        )
        logger.info("Supabase checkpointer created successfully")
        return checkpointer

    except ImportError as e:
        logger.warning(f"Supabase checkpointer import failed: {e}")
        logger.info("Falling back to in-memory checkpointer")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    except Exception as e:
        logger.error(f"Failed to create Supabase checkpointer: {e}")
        logger.info("Falling back to in-memory checkpointer")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


def get_checkpointer_config(thread_id: str) -> dict[str, Any]:
    """Build LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}
