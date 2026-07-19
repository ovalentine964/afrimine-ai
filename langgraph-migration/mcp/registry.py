"""
AfriMine AI — MCP Server Registry
===================================
Central registry for all MCP servers. Used by LangGraph agents to discover
and connect to available MCP tools.

Usage:
    from mcp.registry import mcp_registry
    tools = mcp_registry.get_tools_for_agent("geology")
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_mcp import BaseMCPServer, MCPTool

# Import all MCP servers
from .satellite_mcp import SatelliteMCPServer
from .geology_mcp import GeologyMCPServer
from .market_mcp import MarketMCPServer
from .sample_mcp import SampleMCPServer
from .mineral_classifier_mcp import MineralClassifierMCPServer
from .compliance_mcp import ComplianceMCPServer
from .report_mcp import ReportMCPServer
from .image_processor_mcp import ImageProcessorMCPServer
from .economics_mcp import EconomicsMCPServer
from .regulatory_mcp import RegulatoryMCPServer
from .storage_mcp import StorageMCPServer
from .geostats_mcp import GeostatsMCPServer

logger = logging.getLogger(__name__)

# Agent → MCP server mapping (mirrors security/mcp_access_control.py)
AGENT_MCP_SERVERS = {
    "sampling": ["satellite-mcp", "geology-mcp", "sample-mcp"],
    "analysis": ["mineral-classifier-mcp", "image-processor-mcp", "sample-mcp"],
    "geology": ["geology-mcp", "satellite-mcp", "geostats-mcp"],
    "market": ["market-mcp", "economics-mcp"],
    "report": ["report-mcp", "storage-mcp"],
    "compliance": ["compliance-mcp", "regulatory-mcp"],
}


class MCPRegistry:
    """Central registry of all AfriMine MCP servers."""

    def __init__(self, supabase_client=None):
        self._servers: Dict[str, BaseMCPServer] = {}
        self._supabase = supabase_client

    def initialize_all(self):
        """Initialize all MCP servers."""
        server_classes = [
            SatelliteMCPServer,
            GeologyMCPServer,
            MarketMCPServer,
            SampleMCPServer,
            MineralClassifierMCPServer,
            ComplianceMCPServer,
            ReportMCPServer,
            ImageProcessorMCPServer,
            EconomicsMCPServer,
            RegulatoryMCPServer,
            StorageMCPServer,
            GeostatsMCPServer,
        ]

        for cls in server_classes:
            try:
                # Pass supabase_client to servers that need it
                if cls in (GeologyMCPServer, MarketMCPServer, SampleMCPServer,
                           ComplianceMCPServer, StorageMCPServer):
                    server = cls(supabase_client=self._supabase)
                else:
                    server = cls()
                self._servers[server.name] = server
                logger.info(f"Initialized MCP server: {server.name}")
            except Exception as e:
                logger.error(f"Failed to initialize {cls.__name__}: {e}")

        logger.info(f"MCP registry: {len(self._servers)} servers initialized")

    def get_server(self, name: str) -> Optional[BaseMCPServer]:
        return self._servers.get(name)

    def get_tools_for_agent(self, agent_role: str) -> List[MCPTool]:
        """Get all MCP tools available to an agent role."""
        server_names = AGENT_MCP_SERVERS.get(agent_role, [])
        tools = []
        for name in server_names:
            server = self._servers.get(name)
            if server:
                tools.extend(server.get_tools())
        return tools

    async def invoke(self, server_name: str, tool_name: str,
                     parameters: Dict[str, Any],
                     agent_role: Optional[str] = None) -> Dict[str, Any]:
        """Invoke a tool on a specific MCP server."""
        server = self._servers.get(server_name)
        if not server:
            return {"error": f"MCP server '{server_name}' not found"}
        return await server.invoke(tool_name, parameters, agent_role)

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all MCP servers."""
        results = {}
        for name, server in self._servers.items():
            try:
                results[name] = await server.health_check()
            except Exception:
                results[name] = False
        return results


# Global singleton
mcp_registry = MCPRegistry()
