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

import logging
from typing import Any

from config import settings

logger = logging.getLogger("afrimine.checkpoint")


def create_checkpointer(use_memory: bool = False) -> Any:
    """
    Create a LangGraph checkpointer.

    Args:
        use_memory: If True, use in-memory checkpointer (for testing).
                    If False, use Supabase PostgreSQL (production).

    Returns:
        A BaseCheckpointSaver instance.
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
        # Try the dedicated Supabase checkpointer from memory-system/
        import sys
        import os

        # Add memory-system to path for imports
        memory_sys_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "memory-system"
        )
        if os.path.isdir(memory_sys_path):
            sys.path.insert(0, os.path.abspath(memory_sys_path))

        from supabase_checkpointer import SupabaseCheckpointer

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
