"""Logging setup and utilities."""

import logfire

# Clean wrapper that forwards everything to logfire without
# modifying it
logger = type(
    'Logger',
    (),
    {'__getattr__': lambda self, name: getattr(logfire, name)}
)()


def setup(verbose: bool = False):
    """Configure logging for splintercat."""
    # Configure logfire with appropriate verbosity
    # verbose=True shows DEBUG level, False shows INFO level
    logfire.configure(
        console={'verbose': verbose}
    )
    # Instrument pydantic-AI to trace all agent runs, model
    # requests, and tool calls
    logfire.instrument_pydantic_ai()


# Add setup to the wrapper object
logger.setup = setup
