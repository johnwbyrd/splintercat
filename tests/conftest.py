"""Pytest configuration and fixtures for splintercat tests."""

import pytest

from splintercat.core.log import logger


@pytest.fixture(autouse=True, scope="session")
def configure_logging():
    """Configure logging for console-only mode during tests.

    This enables debug output during test runs without requiring
    authentication or sending logs to logfire.dev.
    """
    logger.setup(min_log_level='debug')
