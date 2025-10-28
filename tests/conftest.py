"""Pytest configuration and fixtures for splintercat tests."""

import sys
import tempfile
from pathlib import Path

import pytest

from splintercat.core.log import ConsoleSink, setup_logger


@pytest.fixture(autouse=True, scope="session")
def configure_logging():
    """Configure logging for console-only mode during tests.

    This enables debug output during test runs without requiring
    authentication or sending logs to logfire.dev.
    """
    # Setup global logger for tests with console-only output
    test_log_root = Path(tempfile.gettempdir()) / "splintercat-tests"
    setup_logger(
        log_root=test_log_root,
        merge_name="test",
        console=ConsoleSink(level="debug"),
    )


@pytest.fixture(scope="session")
def test_config():
    """Load configuration for tests without CLI parsing conflicts.

    Creates a State object with full configuration loading, but
    temporarily replaces sys.argv to avoid conflicts with pytest's
    command line arguments.

    Returns:
        Config object with all settings loaded from defaults
    """
    from splintercat.core.config import State

    # Temporarily replace sys.argv to avoid CLI parsing conflicts
    old_argv = sys.argv
    sys.argv = ['splintercat']  # Minimal argv that satisfies parsers

    try:
        state = State()
        return state.config
    finally:
        sys.argv = old_argv
