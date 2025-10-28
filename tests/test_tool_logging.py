"""Test tool logging improvements."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.tools import workspace_tools
from splintercat.tools.workspace import Workspace


def test_tool_logging_on_success():
    """Test that successful tool calls log invocation and results."""
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        test_file = workdir / "test.txt"
        test_file.write_text("Hello World\n")

        workspace = Workspace(
            workdir=workdir,
            conflict_files=["test.txt"],
            config=None,
        )

        # Create context
        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        # Find the wrapped read_file in workspace_tools
        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        # Mock logger to capture calls
        with patch('splintercat.tools.logger') as mock_logger:
            # Call tool
            read_file_wrapped(ctx, "test.txt", start_line=1, num_lines=10)

            # Verify invocation was logged
            assert mock_logger.info.called
            invocation_calls = [
                call for call in mock_logger.info.call_args_list
                if "invoked" in str(call)
            ]
            assert len(invocation_calls) > 0

            # Verify success was logged
            success_calls = [
                call for call in mock_logger.info.call_args_list
                if "succeeded" in str(call)
            ]
            assert len(success_calls) > 0

            # Verify result was logged at trace level
            assert mock_logger.trace.called


def test_tool_logging_on_model_retry():
    """Test that ModelRetry exceptions are logged with context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)

        workspace = Workspace(
            workdir=workdir,
            conflict_files=[],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        # Find the wrapped read_file in workspace_tools
        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        # Mock logger
        with patch('splintercat.tools.logger') as mock_logger:
            # Try to read non-existent file (should raise ModelRetry)
            with pytest.raises(ModelRetry):
                read_file_wrapped(ctx, "nonexistent.txt")

            # Verify ModelRetry was logged as warning
            assert mock_logger.warning.called
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if "ModelRetry" in str(call)
            ]
            assert len(warning_calls) > 0

            # Verify the warning includes retry_message
            warning_call = warning_calls[0]
            assert 'retry_message' in str(warning_call)


def test_tool_logging_on_unexpected_error():
    """Test that unexpected exceptions are logged with full context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)

        workspace = Workspace(
            workdir=workdir,
            conflict_files=[],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        # Find wrapped write_file
        write_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'write_file'
        )

        # Mock logger
        with patch('splintercat.tools.logger') as mock_logger:
            # Create a scenario that raises an exception
            # (write to a path that can't be created)
            with pytest.raises(PermissionError):
                # Make workdir read-only to force write failure
                import os
                original_mode = workdir.stat().st_mode
                try:
                    os.chmod(workdir, 0o444)  # Read-only
                    write_file_wrapped(
                        ctx,
                        "subdir/test.txt",
                        "content",
                        confirm_large=True
                    )
                finally:
                    os.chmod(workdir, original_mode)

            # Verify error was logged
            assert mock_logger.error.called
            error_calls = [
                call for call in mock_logger.error.call_args_list
                if "unexpected exception" in str(call)
            ]
            assert len(error_calls) > 0


def test_tool_logging_includes_execution_time():
    """Test that tool execution time is logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        test_file = workdir / "test.txt"
        test_file.write_text("content")

        workspace = Workspace(
            workdir=workdir,
            conflict_files=["test.txt"],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        with patch('splintercat.tools.logger') as mock_logger:
            read_file_wrapped(ctx, "test.txt")

            # Check that execution_time_ms was logged
            all_calls = str(mock_logger.info.call_args_list)
            assert 'execution_time_ms' in all_calls


def test_tool_logging_includes_workspace_context():
    """Test that workspace info is included in logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        test_file = workdir / "test.txt"
        test_file.write_text("content")

        workspace = Workspace(
            workdir=workdir,
            conflict_files=["file1.txt", "file2.txt"],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        with patch('splintercat.tools.logger') as mock_logger:
            read_file_wrapped(ctx, "test.txt")

            # Check that workspace context was logged
            all_calls = str(mock_logger.info.call_args_list)
            assert 'workspace_workdir' in all_calls
            assert 'conflict_files' in all_calls
            assert str(workdir) in all_calls
