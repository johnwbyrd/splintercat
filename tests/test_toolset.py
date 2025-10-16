"""Tests for workspace tools."""

from splintercat.tools import workspace_tools


def test_workspace_tools_list():
    """Test that workspace tools list contains all expected tools."""
    # Should have 6 tools (added run_command and list_allowed_commands)
    assert len(workspace_tools) == 6

    # Get tool names
    tool_names = {tool.__name__ for tool in workspace_tools}

    # Check all expected tools are present
    assert "run_command" in tool_names
    assert "list_allowed_commands" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "concatenate_to_file" in tool_names
    assert "submit_resolution" in tool_names
