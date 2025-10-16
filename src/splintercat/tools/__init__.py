"""Tool system for LLM-based conflict resolution."""

from splintercat.tools.base import Tool
from splintercat.tools.registry import ToolRegistry
from splintercat.tools.workspace import (
    cat_files,
    list_files,
    read_file,
    submit_resolution,
    write_file,
)

# Workspace tools list for use with Agent(tools=[...])
workspace_tools = [
    list_files,
    read_file,
    write_file,
    cat_files,
    submit_resolution,
]

__all__ = [
    "Tool",
    "ToolRegistry",
    "workspace_tools",
    "list_files",
    "read_file",
    "write_file",
    "cat_files",
    "submit_resolution",
]
