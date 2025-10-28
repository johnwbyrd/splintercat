"""Integration test showing improved tool logging in action.

This demonstrates what the log output looks like with the new logging
system.
Run with: pytest tests/test_tool_logging_integration.py -s
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.core.log import setup_logger
from splintercat.tools import workspace_tools
from splintercat.tools.workspace import Workspace


@pytest.fixture
def setup_test_logger():
    """Set up logger for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from splintercat.core.log import ConsoleSink

        # Configure console-only logging for test visibility
        console = ConsoleSink(
            level="trace",
            verbose=True,
            colors="auto",
        )

        setup_logger(
            log_root=Path(tmpdir),
            merge_name="test-logging",
            console=console,
        )
        yield


def test_successful_tool_execution(setup_test_logger):
    """Demonstrate logging for successful tool execution."""
    print("\n" + "="*70)
    print("TEST: Successful Tool Execution")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        test_file = workdir / "example.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        workspace = Workspace(
            workdir=workdir,
            conflict_files=["example.py"],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        # Find wrapped read_file
        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        # Execute - logs will be visible
        result = read_file_wrapped(
            ctx, "example.py", start_line=1, num_lines=10
        )
        assert "hello" in result

    print("\nExpected log entries:")
    print(
        "  1. Tool 'read_file' invoked - with args and "
        "workspace context"
    )
    print(
        "  2. Tool 'read_file' succeeded - with execution time and "
        "result size"
    )
    print("  3. Full result at TRACE level")


def test_model_retry_logging(setup_test_logger):
    """Demonstrate logging when ModelRetry is raised."""
    print("\n" + "="*70)
    print("TEST: ModelRetry Exception Logging")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)

        workspace = Workspace(
            workdir=workdir,
            conflict_files=[],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        # Try to read non-existent file
        with pytest.raises(ModelRetry) as exc_info:
            read_file_wrapped(ctx, "missing_file.txt")

        print(f"\nModelRetry message: {exc_info.value}")
        print("\nExpected log entries:")
        print("  1. Tool 'read_file' invoked")
        print("  2. WARNING: Tool 'read_file' raised ModelRetry")
        print("     - With retry_message, args, kwargs, workspace context")


def test_validation_error_logging(setup_test_logger):
    """Demonstrate logging for validation errors (large file read)."""
    print("\n" + "="*70)
    print("TEST: Validation Error (Large File Warning)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        test_file = workdir / "large.txt"
        test_file.write_text("line\n" * 300)  # 300 lines

        workspace = Workspace(
            workdir=workdir,
            conflict_files=["large.txt"],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        # Try to read >200 lines without confirmation
        with pytest.raises(ModelRetry) as exc_info:
            read_file_wrapped(ctx, "large.txt", start_line=1, num_lines=-1)

        print(f"\nModelRetry message: {exc_info.value}")
        print("\nExpected log entries:")
        print("  1. Tool 'read_file' invoked")
        print("  2. WARNING: Tool 'read_file' raised ModelRetry")
        print("     - retry_message explains the 200 line limit")
        print("     - args shows num_lines=-1 was requested")


def test_multiple_tools_sequence(setup_test_logger):
    """Demonstrate logging for a sequence of tool calls."""
    print("\n" + "="*70)
    print("TEST: Multiple Tool Calls in Sequence")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)

        workspace = Workspace(
            workdir=workdir,
            conflict_files=["output.txt"],
            config=None,
        )

        ctx = MagicMock(spec=RunContext)
        ctx.deps = workspace

        # Find wrapped tools
        write_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'write_file'
        )
        read_file_wrapped = next(
            tool for tool in workspace_tools
            if tool.__name__ == 'read_file'
        )

        # Write then read
        write_file_wrapped(ctx, "output.txt", "Hello, World!")
        result = read_file_wrapped(ctx, "output.txt")

        assert "Hello" in result

        print("\nExpected log entries:")
        print("  1. Tool 'write_file' invoked")
        print("  2. Tool 'write_file' succeeded")
        print("  3. Tool 'read_file' invoked")
        print("  4. Tool 'read_file' succeeded")
        print("\nEach with execution times showing performance")


if __name__ == "__main__":
    # Run with: python tests/test_tool_logging_integration.py
    pytest.main([__file__, "-s", "-v"])
