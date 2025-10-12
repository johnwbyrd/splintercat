"""Tool registry for managing LLM tools."""

from splintercat.tools.base import Tool


class ToolRegistry:
    """Registry for LLM tools.

    Manages tool registration and provides schemas for function calling.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool to register
        """
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        """Retrieve tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance

        Raises:
            KeyError: If tool not found
        """
        return self._tools[name]

    def get_schemas(self) -> list[dict]:
        """Get function schemas for all tools.

        Returns:
            List of function schema dicts
        """
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return schemas

    def execute_tool(self, name: str, **kwargs) -> str:
        """Execute tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        tool = self.get_tool(name)
        return tool.execute(**kwargs)
