"""Logging setup and utilities."""

import sys

from loguru import logger


def setup_logging(verbose: bool = False):
    """Configure logging for splintercat.

    Args:
        verbose: If True, set console output to DEBUG level, otherwise INFO
    """
    # Remove default handler
    logger.remove()

    # Console output - INFO or DEBUG based on verbose flag
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )

    # File logging with rotation and retention
    logger.add("splintercat.log", rotation="10 MB", retention="3 days", level="DEBUG")
