"""Tests for workspace tools."""

from splintercat.tools import workspace_tools


def test_workspace_tools_list():
    """Test that workspace tools list contains all expected tools."""
    # Should have 5 tools
    assert len(workspace_tools) == 5

    # Get tool names
    tool_names = {tool.__name__ for tool in workspace_tools}

    # Check all expected tools are present
    assert "list_files" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "cat_files" in tool_names
    assert "submit_resolution" in tool_names
