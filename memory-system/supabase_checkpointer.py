"""
AfriMine AI — Supabase Checkpointer for LangGraph

Implements LangGraph's BaseCheckpointSaver interface using Supabase (PostgreSQL).
This enables durable execution: if a pipeline crashes at step 4, it resumes
from step 4, not step 1.

Compatible with langgraph-checkpoint-postgres protocol but uses Supabase client
for zero-cost hosting.

Usage:
    from langgraph.graph import StateGraph

    checkpointer = SupabaseCheckpointer(supabase_url="...", supabase_key="...")
    graph = builder.compile(checkpointer=checkpointer)

    # Run with thread_id for checkpointing
    config = {"configurable": {"thread_id": "analysis-001"}}
    result = graph.invoke(input_data, config=config)

    # Resume from checkpoint
    result = graph.invoke(None, config=config)  # Continues from last checkpoint
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional
from datetime import datetime, timezone

import orjson
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    PendingWrite,
)

logger = logging.getLogger("afrimine.checkpoint")

# Serialization helpers
def _serialize(obj: Any) -> str:
    """Serialize to JSON string for Supabase JSONB columns."""
    return orjson.dumps(obj).decode("utf-8")


def _deserialize(data: str | dict | None) -> Any:
    """Deserialize from JSON string or dict."""
    if data is None:
        return None
    if isinstance(data, str):
        return orjson.loads(data)
    return data


class SupabaseCheckpointer(BaseCheckpointSaver):
    """
    LangGraph checkpoint saver backed by Supabase (PostgreSQL).

    Stores checkpoint data in the `checkpoints` and `checkpoint_writes` tables.
    Supports:
        - Full state snapshots per graph step
        - Parent checkpoint chaining (for time-travel debugging)
        - Concurrent pipeline runs (isolated by thread_id)
        - Automatic cleanup of old checkpoints
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        max_checkpoints_per_thread: int = 50,
    ):
        super().__init__()
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_KEY", "")
        self.max_checkpoints_per_thread = max_checkpoints_per_thread
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from supabase import create_client
            self._client = create_client(self.supabase_url, self.supabase_key)
        return self._client

    # -------------------------------------------------------------------------
    # BaseCheckpointSaver interface
    # -------------------------------------------------------------------------

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """
        Get the latest checkpoint for a thread.

        Returns None if no checkpoint exists (fresh start).
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        result = (
            self.client.table("checkpoints")
            .select("*")
            .eq("thread_id", thread_id)
            .eq("checkpoint_ns", checkpoint_ns)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        row = result.data[0]
        checkpoint_data = _deserialize(row["checkpoint"])
        metadata = _deserialize(row["metadata"])

        # Reconstruct Checkpoint object
        checkpoint = Checkpoint(
            v=checkpoint_data.get("v", 1),
            id=row["checkpoint_id"],
            ts=checkpoint_data.get("ts", row["created_at"]),
            channel_values=checkpoint_data.get("channel_values", {}),
            channel_versions=checkpoint_data.get("channel_versions", {}),
            versions_seen=checkpoint_data.get("versions_seen", {}),
        )

        # Get pending writes for this checkpoint
        writes_result = (
            self.client.table("checkpoint_writes")
            .select("*")
            .eq("thread_id", thread_id)
            .eq("checkpoint_ns", checkpoint_ns)
            .eq("checkpoint_id", row["checkpoint_id"])
            .order("idx")
            .execute()
        )

        pending_writes = []
        for w in (writes_result.data or []):
            pending_writes.append((
                w["task_id"],
                w["channel"],
                _deserialize(w["value"]),
            ))

        # Build parent config if exists
        parent_config = None
        if row.get("parent_checkpoint"):
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": row["parent_checkpoint"],
                }
            }

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": row["checkpoint_id"],
                }
            },
            checkpoint=checkpoint,
            metadata=metadata or {},
            parent_config=parent_config,
            pending_writes=pending_writes if pending_writes else None,
        )

    def list(
        self,
        config: RunnableConfig,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> list[CheckpointTuple]:
        """List checkpoints for a thread, newest first."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        query = (
            self.client.table("checkpoints")
            .select("*")
            .eq("thread_id", thread_id)
            .eq("checkpoint_ns", checkpoint_ns)
            .order("created_at", desc=True)
        )

        if limit:
            query = query.limit(limit)
        if before and "configurable" in before:
            before_id = before["configurable"].get("checkpoint_id")
            if before_id:
                # Get the timestamp of the 'before' checkpoint
                before_row = (
                    self.client.table("checkpoints")
                    .select("created_at")
                    .eq("checkpoint_id", before_id)
                    .single()
                    .execute()
                )
                if before_row.data:
                    query = query.lt("created_at", before_row.data["created_at"])

        result = query.execute()
        tuples = []

        for row in (result.data or []):
            checkpoint_data = _deserialize(row["checkpoint"])
            metadata = _deserialize(row["metadata"]) or {}

            # Apply filter
            if filter:
                match = all(metadata.get(k) == v for k, v in filter.items())
                if not match:
                    continue

            checkpoint = Checkpoint(
                v=checkpoint_data.get("v", 1),
                id=row["checkpoint_id"],
                ts=checkpoint_data.get("ts", ""),
                channel_values=checkpoint_data.get("channel_values", {}),
                channel_versions=checkpoint_data.get("channel_versions", {}),
                versions_seen=checkpoint_data.get("versions_seen", {}),
            )

            parent_config = None
            if row.get("parent_checkpoint"):
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": row["parent_checkpoint"],
                    }
                }

            tuples.append(
                CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": row["checkpoint_id"],
                        }
                    },
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config,
                )
            )

        return tuples

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        Save a checkpoint. Called by LangGraph after each graph step.

        This is the hot path — must be fast and reliable.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]

        # Get parent checkpoint (the previous one for this thread)
        parent_checkpoint_id = None
        existing = (
            self.client.table("checkpoints")
            .select("checkpoint_id")
            .eq("thread_id", thread_id)
            .eq("checkpoint_ns", checkpoint_ns)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing.data:
            parent_checkpoint_id = existing.data[0]["checkpoint_id"]
            # Don't parent to self
            if parent_checkpoint_id == checkpoint_id:
                parent_checkpoint_id = None

        # Serialize checkpoint data
        checkpoint_data = {
            "v": checkpoint.get("v", 1),
            "ts": checkpoint.get("ts", datetime.now(timezone.utc).isoformat()),
            "channel_values": checkpoint.get("channel_values", {}),
            "channel_versions": checkpoint.get("channel_versions", {}),
            "versions_seen": checkpoint.get("versions_seen", {}),
        }

        # Upsert checkpoint
        row = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "parent_checkpoint": parent_checkpoint_id,
            "checkpoint": _serialize(checkpoint_data),
            "metadata": _serialize(dict(metadata) if metadata else {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self.client.table("checkpoints").upsert(
            row,
            on_conflict="thread_id,checkpoint_ns,checkpoint_id",
        ).execute()

        # Cleanup old checkpoints for this thread
        self._cleanup_old_checkpoints(thread_id, checkpoint_ns)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Save pending writes for a checkpoint.
        Writes are channel updates that haven't been committed yet.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        rows = []
        for idx, (channel, value) in enumerate(writes):
            rows.append({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "idx": idx,
                "channel": channel,
                "value": _serialize(value),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        if rows:
            self.client.table("checkpoint_writes").upsert(
                rows,
                on_conflict="thread_id,checkpoint_ns,checkpoint_id,task_id,idx",
            ).execute()

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _cleanup_old_checkpoints(self, thread_id: str, checkpoint_ns: str) -> None:
        """Remove checkpoints beyond the retention limit for a thread."""
        # Count checkpoints for this thread
        count_result = (
            self.client.table("checkpoints")
            .select("checkpoint_id", count="exact")
            .eq("thread_id", thread_id)
            .eq("checkpoint_ns", checkpoint_ns)
            .execute()
        )

        total = count_result.count if hasattr(count_result, "count") else len(count_result.data or [])
        if total <= self.max_checkpoints_per_thread:
            return

        # Get oldest checkpoints to delete
        excess = total - self.max_checkpoints_per_thread
        old = (
            self.client.table("checkpoints")
            .select("checkpoint_id")
            .eq("thread_id", thread_id)
            .eq("checkpoint_ns", checkpoint_ns)
            .order("created_at", desc=False)
            .limit(excess)
            .execute()
        )

        for row in (old.data or []):
            cid = row["checkpoint_id"]
            # Delete writes first (foreign key)
            self.client.table("checkpoint_writes").delete().eq(
                "thread_id", thread_id
            ).eq("checkpoint_ns", checkpoint_ns).eq(
                "checkpoint_id", cid
            ).execute()
            # Delete checkpoint
            self.client.table("checkpoints").delete().eq(
                "thread_id", thread_id
            ).eq("checkpoint_ns", checkpoint_ns).eq(
                "checkpoint_id", cid
            ).execute()

        logger.debug(
            "Cleaned up %d old checkpoints for thread %s", excess, thread_id
        )

    def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints for a thread (cleanup after analysis)."""
        self.client.table("checkpoint_writes").delete().eq(
            "thread_id", thread_id
        ).execute()
        self.client.table("checkpoints").delete().eq(
            "thread_id", thread_id
        ).execute()
        logger.info("Deleted all checkpoints for thread %s", thread_id)

    def get_latest_state(self, config: RunnableConfig) -> dict[str, Any] | None:
        """Convenience: get the latest checkpoint state as a plain dict."""
        tuple = self.get_tuple(config)
        if tuple is None:
            return None
        return tuple.checkpoint.get("channel_values", {})
