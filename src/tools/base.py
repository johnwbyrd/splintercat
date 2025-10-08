"""Base tool interface."""

from typing import Protocol


class Tool(Protocol):
    """Protocol for LLM tools.

    Tools provide functionality that LLMs can invoke via function calling.
    """

    @property
    def name(self) -> str:
        """Tool identifier for LLM."""
        pass

    @property
    def description(self) -> str:
        """What the tool does (for function schema)."""
        pass

    @property
    def parameters(self) -> dict:
        """JSON schema of parameters."""
        pass

    def execute(self, **kwargs) -> str:
        """Execute tool with parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Human-readable result text
        """
        pass
