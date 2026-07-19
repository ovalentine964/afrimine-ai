"""
AfriMine AI — Supabase Checkpointer Setup
==========================================

Configures the PostgreSQL checkpointer for LangGraph durable execution.
Uses Supabase's free-tier PostgreSQL (500MB) for state persistence.

Why a checkpointer matters for AfriMine:
- Pipeline crashes at step 4 → resume from step 4, not step 1
- Field workers lose connectivity → state preserved server-side
- Investor reports need audit trail → full state history in Postgres
- Concurrent analyses → each gets isolated checkpoint namespace

Connection strategy:
1. Production: Supabase PostgreSQL via DATABASE_URL
2. Development: Local PostgreSQL or SQLite fallback
3. Testing: In-memory checkpointer (no persistence)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


def get_checkpointer(
    database_url: Optional[str] = None,
    *,
    use_memory: bool = False,
) -> BaseCheckpointSaver:
    """
    Create the appropriate checkpointer based on environment.

    Args:
        database_url: PostgreSQL connection string.
                      Falls back to DATABASE_URL env var.
        use_memory: If True, return in-memory checkpointer (for tests).

    Returns:
        A checkpoint saver compatible with LangGraph StateGraph.compile().

    Raises:
        ValueError: If no database URL is provided and not using memory.
        ImportError: If langgraph-checkpoint-postgres is not installed.
    """
    if use_memory:
        logger.info("Using in-memory checkpointer (no persistence)")
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()

    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "No DATABASE_URL found. Set the environment variable or pass "
            "database_url explicitly. For Supabase, use the connection string "
            "from Settings → Database → Connection string → URI."
        )

    # Mask credentials for logging
    safe_url = url.split("@")[-1] if "@" in url else url
    logger.info(f"Connecting to PostgreSQL checkpointer: ...@{safe_url}")

    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        # PostgresSaver.from_conn_string handles connection pooling internally.
        # For Supabase, the connection string includes sslmode=require.
        checkpointer = PostgresSaver.from_conn_string(url)

        # Run migrations to create checkpoint tables if they don't exist.
        # This is idempotent — safe to call on every startup.
        checkpointer.setup()

        logger.info("PostgreSQL checkpointer initialized and tables verified")
        return checkpointer

    except ImportError:
        logger.warning(
            "langgraph-checkpoint-postgres not installed. "
            "Falling back to in-memory checkpointer. "
            "Install with: pip install langgraph-checkpoint-postgres"
        )
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()


def get_supabase_url() -> str:
    """
    Construct the Supabase PostgreSQL connection URL from environment.

    Expected env vars (set in .env or Cloudflare Workers):
        SUPABASE_DB_HOST: e.g. db.xxxxx.supabase.co
        SUPABASE_DB_PASSWORD: Your database password
        SUPABASE_DB_NAME: Usually "postgres"
        SUPABASE_DB_USER: Usually "postgres"
        SUPABASE_DB_PORT: Usually 5432

    Returns:
        PostgreSQL connection URL with SSL.
    """
    host = os.environ.get("SUPABASE_DB_HOST", "")
    password = os.environ.get("SUPABASE_DB_PASSWORD", "")
    dbname = os.environ.get("SUPABASE_DB_NAME", "postgres")
    user = os.environ.get("SUPABASE_DB_USER", "postgres")
    port = os.environ.get("SUPABASE_DB_PORT", "5432")

    if not host or not password:
        raise ValueError(
            "SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD must be set. "
            "Find these in Supabase Dashboard → Settings → Database."
        )

    return (
        f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        f"?sslmode=require"
    )
