"""Logging setup and utilities."""

import logfire

# Clean wrapper that forwards everything to logfire without
# modifying it
logger = type(
    'Logger',
    (),
    {'__getattr__': lambda self, name: getattr(logfire, name)}
)()


def setup(min_log_level: str = 'info'):
    """Configure logging for splintercat.

    Args:
        min_log_level: Minimum log level to display
            ('trace', 'debug', 'info', 'warn', 'error', 'fatal')
    """
    from logfire import ConsoleOptions

    logfire.configure(
        console=ConsoleOptions(
            min_log_level=min_log_level,
            verbose=True  # Show full span details including tool calls and arguments
        )
    )
    # Instrument pydantic-AI to trace all agent runs, model
    # requests, and tool calls
    logfire.instrument_pydantic_ai()


# Add setup to the wrapper object
logger.setup = setup
