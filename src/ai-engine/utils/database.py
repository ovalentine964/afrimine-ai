"""
AfriMine AI — Supabase Database Client
Provides database connectivity for storing and retrieving analysis results.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("supabase-py not installed — database features disabled")


_supabase_client: Optional[Client] = None


def get_supabase_client(
    url: Optional[str] = None,
    key: Optional[str] = None,
) -> Optional[Client]:
    """
    Get or create a Supabase client instance.

    Uses environment variables SUPABASE_URL and SUPABASE_KEY if not provided.

    Returns None if supabase is not installed or credentials are missing.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_AVAILABLE:
        logger.warning("Cannot create Supabase client: supabase-py not installed")
        return None

    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        logger.warning("Cannot create Supabase client: SUPABASE_URL or SUPABASE_KEY not set")
        return None

    try:
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized: %s", url)
        return _supabase_client
    except Exception as e:
        logger.error("Failed to initialize Supabase client: %s", e)
        return None


def save_analysis_result(result: dict, table: str = "analysis_results") -> Optional[dict]:
    """
    Save an analysis result to Supabase.

    Parameters
    ----------
    result : dict
        Analysis result to store.
    table : str
        Supabase table name.

    Returns
    -------
    dict or None
        Inserted record, or None on failure.
    """
    client = get_supabase_client()
    if client is None:
        logger.warning("Supabase not available — result not saved")
        return None

    try:
        response = client.table(table).insert(result).execute()
        logger.info("Saved analysis result to %s", table)
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error("Failed to save analysis result: %s", e)
        return None


def get_analysis_results(
    table: str = "analysis_results",
    filters: Optional[dict] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Retrieve analysis results from Supabase.

    Parameters
    ----------
    table : str
        Supabase table name.
    filters : dict, optional
        Column filters, e.g. {"mineral": "gold"}.
    limit : int
        Maximum records to return.

    Returns
    -------
    list of dict
    """
    client = get_supabase_client()
    if client is None:
        return []

    try:
        query = client.table(table).select("*")
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        response = query.limit(limit).execute()
        return response.data or []
    except Exception as e:
        logger.error("Failed to query Supabase: %s", e)
        return []


def save_block_model(model_data: dict, table: str = "block_models") -> Optional[dict]:
    """Save block model data to Supabase."""
    client = get_supabase_client()
    if client is None:
        return None

    try:
        response = client.table(table).insert(model_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error("Failed to save block model: %s", e)
        return None
