"""
AfriMine AI — MCP Server Base Class
====================================
Abstract base for all AfriMine MCP servers.
Provides common patterns: tool registration, health checks, error handling.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Definition of an MCP tool."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for parameters
    handler: Callable[..., Any]
    required_permissions: List[str] = field(default_factory=list)


class BaseMCPServer(ABC):
    """
    Abstract base class for AfriMine MCP servers.

    Each MCP server:
    - Exposes a set of tools (functions) that LangGraph agents can call
    - Validates permissions before tool execution
    - Logs all tool invocations for audit trail
    - Handles errors gracefully with fallback responses

    Usage:
        class MyServer(BaseMCPServer):
            name = "my-mcp"
            version = "1.0.0"

            def _register_tools(self):
                self.register_tool(MCPTool(...))

            async def health_check(self):
                return True
    """

    name: str = "base-mcp"
    version: str = "0.0.1"

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._register_tools()
        logger.info(f"MCP server '{self.name}' initialized with {len(self._tools)} tools")

    def _register_tools(self):
        """Override to register tools. Called during __init__."""
        pass

    def register_tool(self, tool: MCPTool):
        """Register a tool with this MCP server."""
        self._tools[tool.name] = tool
        logger.debug(f"[{self.name}] Registered tool: {tool.name}")

    def get_tools(self) -> List[MCPTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a specific tool by name."""
        return self._tools.get(name)

    async def invoke(self, tool_name: str, parameters: Dict[str, Any],
                     agent_role: Optional[str] = None) -> Dict[str, Any]:
        """
        Invoke a tool by name.

        Args:
            tool_name: Name of the tool to invoke
            parameters: Tool parameters
            agent_role: The calling agent's role (for permission checks)

        Returns:
            Tool result as a dict
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found in {self.name}"}

        # Permission check
        if tool.required_permissions and agent_role:
            if agent_role not in tool.required_permissions:
                return {"error": f"Agent '{agent_role}' lacks permission for tool '{tool_name}'"}

        try:
            logger.info(f"[{self.name}] Invoking tool '{tool_name}' (agent={agent_role})")
            result = await tool.handler(**parameters)
            logger.info(f"[{self.name}] Tool '{tool_name}' completed successfully")
            return {"result": result, "tool": tool_name, "server": self.name}
        except Exception as e:
            logger.error(f"[{self.name}] Tool '{tool_name}' failed: {e}")
            return {"error": str(e), "tool": tool_name, "server": self.name}

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this MCP server is healthy and ready to serve."""
        pass

    def get_server_info(self) -> Dict[str, Any]:
        """Return server metadata (for MCP discovery)."""
        return {
            "name": self.name,
            "version": self.version,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
                for t in self._tools.values()
            ],
        }
