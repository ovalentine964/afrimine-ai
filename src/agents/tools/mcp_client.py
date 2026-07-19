"""
AfriMine AI — MCP Client
==========================

Connects to MCP (Model Context Protocol) servers for tool access.
Each agent binds to specific servers per the security access control map.

The 12 MCP servers:
    satellite-mcp, geology-mcp, market-mcp, compliance-mcp,
    report-mcp, mineral-classifier-mcp, image-processor-mcp,
    economics-mcp, regulatory-mcp, storage-mcp, geostats-mcp, sample-mcp

Usage:
    client = MCPClient()
    tools = await client.get_tools_for_agent("geology")
    result = await client.call_tool("geology-mcp", "query_knowledge", {"q": "gold pathfinders"})
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

import httpx

from config import settings

logger = logging.getLogger("afrimine.mcp")

# ── Per-Agent MCP Access Control ──────────────────────────────────────────
AGENT_MCP_ACCESS: dict[str, set[str]] = {
    "sampling": {"satellite-mcp", "geology-mcp"},
    "analysis": {"mineral-classifier-mcp", "image-processor-mcp"},
    "geology": {"geology-mcp", "satellite-mcp", "geostats-mcp"},
    "market": {"market-mcp", "economics-mcp"},
    "report": {"report-mcp", "storage-mcp"},
    "compliance": {"compliance-mcp", "regulatory-mcp"},
}

# ── MCP Server Endpoints ──────────────────────────────────────────────────
# In production, these are separate processes/services.
# For MVP, many are in-process function calls.
MCP_SERVER_URLS: dict[str, str] = {
    "satellite-mcp": os.environ.get("MCP_SATELLITE_URL", "http://localhost:8010"),
    "geology-mcp": os.environ.get("MCP_GEOLOGY_URL", "http://localhost:8011"),
    "market-mcp": os.environ.get("MCP_MARKET_URL", "http://localhost:8012"),
    "compliance-mcp": os.environ.get("MCP_COMPLIANCE_URL", "http://localhost:8013"),
    "report-mcp": os.environ.get("MCP_REPORT_URL", "http://localhost:8014"),
    "mineral-classifier-mcp": os.environ.get("MCP_MINERAL_URL", "http://localhost:8015"),
    "image-processor-mcp": os.environ.get("MCP_IMAGE_URL", "http://localhost:8016"),
    "economics-mcp": os.environ.get("MCP_ECONOMICS_URL", "http://localhost:8017"),
    "regulatory-mcp": os.environ.get("MCP_REGULATORY_URL", "http://localhost:8018"),
    "storage-mcp": os.environ.get("MCP_STORAGE_URL", "http://localhost:8019"),
    "geostats-mcp": os.environ.get("MCP_GEOSTATS_URL", "http://localhost:8020"),
    "sample-mcp": os.environ.get("MCP_SAMPLE_URL", "http://localhost:8021"),
}


class MCPClient:
    """
    Client for calling MCP server tools.

    For MVP, falls back to in-process function calls when MCP servers
    are not running as separate services.
    """

    def __init__(self):
        self._http_client: httpx.AsyncClient | None = None
        self._local_handlers: dict[str, dict[str, Callable]] = {}
        self._register_local_handlers()

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    def _register_local_handlers(self) -> None:
        """Register in-process fallback handlers for when MCP servers are unavailable."""
        self._local_handlers = {
            "market-mcp": {
                "fetch_gold_price": self._local_fetch_gold_price,
                "fetch_copper_price": self._local_fetch_copper_price,
            },
            "geology-mcp": {
                "query_knowledge": self._local_query_knowledge,
            },
            "compliance-mcp": {
                "check_license": self._local_check_license,
            },
        }

    async def get_tools_for_agent(self, agent_role: str) -> list[dict[str, Any]]:
        """Get available tool definitions for an agent role."""
        servers = AGENT_MCP_ACCESS.get(agent_role, set())
        tools = []

        for server_name in servers:
            try:
                server_tools = await self._discover_tools(server_name)
                tools.extend(server_tools)
            except Exception as e:
                logger.warning(f"Failed to discover tools from {server_name}: {e}")
                # Use local fallback tool definitions
                local = self._local_handlers.get(server_name, {})
                for tool_name in local:
                    tools.append({
                        "name": tool_name,
                        "server": server_name,
                        "description": f"Local fallback for {tool_name}",
                    })

        return tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        params: dict[str, Any],
        agent_role: str | None = None,
    ) -> Any:
        """
        Call a tool on an MCP server.

        Args:
            server_name: MCP server name (e.g. "geology-mcp")
            tool_name: Tool to call (e.g. "query_knowledge")
            params: Tool parameters
            agent_role: If set, validates access control

        Returns:
            Tool result

        Raises:
            PermissionError: If agent_role doesn't have access
            ConnectionError: If server unreachable and no local fallback
        """
        # Access control check
        if agent_role:
            allowed = AGENT_MCP_ACCESS.get(agent_role, set())
            if server_name not in allowed:
                raise PermissionError(
                    f"Agent '{agent_role}' cannot access '{server_name}'. "
                    f"Allowed: {allowed}"
                )

        # Try remote MCP server first
        try:
            return await self._call_remote(server_name, tool_name, params)
        except Exception as e:
            logger.warning(f"Remote call failed for {server_name}/{tool_name}: {e}")

        # Fall back to local handler
        local = self._local_handlers.get(server_name, {})
        if tool_name in local:
            logger.info(f"Using local fallback for {server_name}/{tool_name}")
            return await local[tool_name](params)

        raise ConnectionError(
            f"No handler available for {server_name}/{tool_name}"
        )

    async def _discover_tools(self, server_name: str) -> list[dict[str, Any]]:
        """Discover tools from an MCP server via HTTP."""
        url = MCP_SERVER_URLS.get(server_name)
        if not url:
            return []

        try:
            client = await self._get_http()
            resp = await client.get(f"{url}/tools", timeout=5.0)
            resp.raise_for_status()
            return resp.json().get("tools", [])
        except Exception:
            return []

    async def _call_remote(
        self, server_name: str, tool_name: str, params: dict[str, Any]
    ) -> Any:
        """Call a tool on a remote MCP server via HTTP."""
        url = MCP_SERVER_URLS.get(server_name)
        if not url:
            raise ConnectionError(f"No URL configured for {server_name}")

        client = await self._get_http()
        resp = await client.post(
            f"{url}/tools/{tool_name}",
            json=params,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Local Fallback Handlers ────────────────────────────────────────────

    async def _local_fetch_gold_price(self, params: dict) -> dict:
        """Fallback gold price fetcher."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="1d")
            if not hist.empty:
                return {"price_usd_oz": round(float(hist["Close"].iloc[-1]), 2)}
        except Exception:
            pass
        return {"price_usd_oz": 2350.0, "source": "fallback"}

    async def _local_fetch_copper_price(self, params: dict) -> dict:
        """Fallback copper price fetcher."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("HG=F")
            hist = ticker.history(period="1d")
            if not hist.empty:
                return {"price_usd_lb": round(float(hist["Close"].iloc[-1]), 2)}
        except Exception:
            pass
        return {"price_usd_lb": 4.20, "source": "fallback"}

    async def _local_query_knowledge(self, params: dict) -> dict:
        """Fallback geological knowledge query."""
        return {
            "results": [],
            "source": "local_fallback",
            "note": "MCP server unavailable — using embedded knowledge in agent prompts",
        }

    async def _local_check_license(self, params: dict) -> dict:
        """Fallback license check."""
        return {
            "license_status": "unknown",
            "note": "License database unavailable — manual verification required",
        }

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
