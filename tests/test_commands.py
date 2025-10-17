"""Tests for command execution tools."""

from unittest.mock import Mock

import pytest
from pydantic_ai import RunContext

from splintercat.tools.commands import get_platform_key, run_command
from splintercat.tools.workspace import Workspace


@pytest.fixture
def temp_workspace(tmp_path, test_config):
    """Create a temporary workspace with test configuration."""
    workspace = Workspace(
        workdir=tmp_path,
        conflict_files=[],
        config=test_config
    )
    return workspace


@pytest.fixture
def mock_ctx(temp_workspace):
    """Create a mock RunContext with workspace."""
    ctx = Mock(spec=RunContext)
    ctx.deps = temp_workspace
    return ctx


def test_grep_with_pipe_regex(mock_ctx, temp_workspace):
    """Test that grep with | in regex pattern works (shell-escaped)."""
    if get_platform_key() == 'windows':
        pytest.skip("POSIX-only test (use findstr on Windows)")

    # Create test file
    (temp_workspace.workdir / "test.txt").write_text(
        "foo\nbar\nbaz\nqux\n"
    )

    # This should work - pipe is properly escaped by shlex.quote
    result = run_command(
        mock_ctx,
        'grep',
        ['-E', 'foo|bar|baz', 'test.txt']
    )

    # Should find matches
    assert "Exit code: 0" in result
    assert "foo" in result
    assert "bar" in result
    assert "baz" in result
    assert "qux" not in result


def test_find_with_wildcard(mock_ctx, temp_workspace):
    """Test that find with * wildcard works (shell-escaped)."""
    if get_platform_key() == 'windows':
        pytest.skip("POSIX-only test (use where on Windows)")

    # Create test files
    (temp_workspace.workdir / "test.cpp").write_text("code")
    (temp_workspace.workdir / "test.py").write_text("code")

    # This should work - * is properly escaped
    result = run_command(
        mock_ctx,
        'find',
        ['.', '-name', '*.cpp']
    )

    assert "Exit code: 0" in result
    assert "test.cpp" in result


def test_command_whitelisting(mock_ctx):
    """Test that non-whitelisted commands are rejected."""
    from pydantic_ai.exceptions import ModelRetry

    # rm is blacklisted on POSIX, del on Windows
    dangerous_cmd = 'rm' if get_platform_key() == 'posix' else 'del'

    with pytest.raises(ModelRetry, match="blacklisted|not allowed"):
        run_command(mock_ctx, dangerous_cmd, ['-rf', '/'])


def test_git_subcommand_validation(mock_ctx):
    """Test that invalid git subcommands are rejected."""
    from pydantic_ai.exceptions import ModelRetry

    with pytest.raises(ModelRetry, match="blacklisted"):
        run_command(mock_ctx, 'git', ['push', 'origin', 'main'])
