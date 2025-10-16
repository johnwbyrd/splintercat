"""Tool system for LLM-based conflict resolution."""

from splintercat.tools.base import Tool
from splintercat.tools.commands import list_allowed_commands, run_command
from splintercat.tools.registry import ToolRegistry
from splintercat.tools.workspace import (
    concatenate_to_file,
    read_file,
    submit_resolution,
    write_file,
)

# Workspace tools list for use with Agent(tools=[...])
workspace_tools = [
    run_command,
    list_allowed_commands,
    read_file,
    write_file,
    concatenate_to_file,
    submit_resolution,
]

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
