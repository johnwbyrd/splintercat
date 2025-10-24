"""Logging setup and utilities."""

from pathlib import Path

import logfire

# Clean wrapper that forwards everything to logfire without
# modifying it
logger = type(
    'Logger',
    (),
    {'__getattr__': lambda self, name: getattr(logfire, name)}
)()


def setup(
    min_log_level: str = 'info',
    agent_log_dir: Path | None = None,
    command: str | None = None,
    project_name: str | None = None
):
    """Configure logging for splintercat.

    Args:
        min_log_level: Minimum log level to display
            ('trace', 'debug', 'info', 'warn', 'error', 'fatal')
        agent_log_dir: Base directory for agent logs (creates
            timestamped subdirectory)
        command: Command name for log directory
            (e.g., 'merge', 'reset')
        project_name: Project name for subdirectory organization
    """
    from logfire import ConsoleOptions
    from logfire._internal.exporters.console import (
        ShowParentsConsoleSpanExporter,
    )
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    from splintercat.core.logdir import AgentLogDir

    additional_processors = []

    # Add file logging if directory and command provided
    if agent_log_dir and command:
        log_dir = AgentLogDir(
            base_dir=agent_log_dir,
            command=command,
            project_name=project_name
        )
        log_file = log_dir.get_log_file()

        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handle = open(log_file, 'w', encoding='utf-8')  # noqa: SIM115
        file_exporter = ShowParentsConsoleSpanExporter(
            output=file_handle,
            colors='never',  # No ANSI codes in file
            include_timestamp=True,
            include_tags=True,
            verbose=True,
            min_log_level=min_log_level
        )
        additional_processors.append(SimpleSpanProcessor(file_exporter))

    logfire.configure(
        console=ConsoleOptions(
            min_log_level=min_log_level,
            verbose=True  # Show full span details
        ),
        additional_span_processors=(
            additional_processors if additional_processors else None
        )
    )
    # Instrument pydantic-AI to trace all agent runs, model
    # requests, and tool calls
    logfire.instrument_pydantic_ai()


# Add setup to the wrapper object
logger.setup = setup
