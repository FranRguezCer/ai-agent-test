"""
Tool Registry System.

This module provides a centralized registry for agent tools.
The registry pattern makes it easy to add new tools without modifying
the core agent code.

To add a new tool:
1. Create a function decorated with @tool from langchain_core.tools
2. Import it here
3. Register it with _registry.register(your_tool)
"""

from typing import Dict
from langchain_core.tools import BaseTool


class ToolRegistry:
    """
    Centralized registry for agent tools.

    This class maintains a dictionary of available tools and provides
    methods to register tools and execute them by name.

    Design benefits:
    - Single source of truth for available tools
    - Easy to add new tools without changing agent code
    - Type-safe tool execution
    """

    def __init__(self):
        """Initialize an empty tool registry."""
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """
        Register a tool in the registry.

        Args:
            tool: A LangChain tool (decorated function with @tool)
        """
        self._tools[tool.name] = tool

    def get_tool_schemas(self) -> list:
        """
        Get all tool schemas for LLM binding.

        The LLM needs to know what tools are available and their schemas
        (name, description, parameters). This method returns them in the
        format expected by LangChain's .bind_tools() method.

        Returns:
            list: List of tool objects ready for LLM binding
        """
        return list(self._tools.values())

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Dictionary of tool parameters

        Returns:
            str: Tool execution result

        Raises:
            ValueError: If tool_name is not registered
        """
        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self._tools[tool_name]
        return tool.invoke(tool_input)


# Global registry instance
# This is a singleton that all parts of the application can use
_registry = ToolRegistry()


# Tool registration happens here
# Import and register tools as they are created
# For now, we'll add the SQL validator in the next file

# Convenience functions for accessing the global registry


def get_tool_schemas() -> list:
    """
    Get all registered tool schemas.

    This is a convenience wrapper around _registry.get_tool_schemas().

    Returns:
        list: List of available tools
    """
    return _registry.get_tool_schemas()


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute a registered tool.

    This is a convenience wrapper around _registry.execute_tool().

    Args:
        tool_name: Name of the tool
        tool_input: Tool parameters

    Returns:
        str: Tool execution result
    """
    return _registry.execute_tool(tool_name, tool_input)


def register_tool(tool: BaseTool):
    """
    Register a tool in the global registry.

    Args:
        tool: The tool to register
    """
    _registry.register(tool)
