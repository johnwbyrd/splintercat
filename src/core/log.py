"""Logging setup and utilities."""

import logfire

# Clean wrapper that forwards everything to logfire without modifying it
logger = type('Logger', (), {'__getattr__': lambda self, name: getattr(logfire, name)})()


def setup(verbose: bool = False):
    """Configure logging for splintercat."""
    # For now, just configure logfire - can add more complex setup later
    logfire.configure()


# Add setup to the wrapper object
logger.setup = setup
