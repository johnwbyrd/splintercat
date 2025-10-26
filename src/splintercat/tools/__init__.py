"""Tool system for LLM-based conflict resolution."""

from functools import wraps

from splintercat.core.log import logger
from splintercat.tools.base import Tool
from splintercat.tools.commands import list_allowed_commands, run_command
from splintercat.tools.registry import ToolRegistry
from splintercat.tools.workspace import (
    concatenate_to_file,
    read_file,
    submit_resolution,
    write_file,
)


def _log_tool_result(func):
    """Decorator to log tool call results centrally.

    Logs the complete return value of tool functions at trace level,
    providing full visibility into what tools are returning to the LLM.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        # Log the complete tool result at trace level
        logger.trace(f"Tool {func.__name__} returned:\n{result}")
        return result
    return wrapper


# Apply logging decorator to all workspace tools centrally
_raw_tools = [
    run_command,
    list_allowed_commands,
    read_file,
    write_file,
    concatenate_to_file,
    submit_resolution,
]

# Workspace tools list for use with Agent(tools=[...])
# All tools are automatically wrapped with result logging
workspace_tools = [_log_tool_result(tool) for tool in _raw_tools]

__all__ = [
    "Tool",
    "ToolRegistry",
    "workspace_tools",
    "run_command",
    "list_allowed_commands",
    "read_file",
    "write_file",
    "concatenate_to_file",
    "submit_resolution",
]
