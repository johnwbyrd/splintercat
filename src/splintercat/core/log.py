"""Unified logging and log directory management."""

from pathlib import Path

import logfire


# LogManager for directory structure management
class LogManager:
    """Centralized log file and directory management.

    Provides structured access to log files organized by category
    and iteration number. Ensures consistent directory creation
    and prevents typos in category names.
    """

    # Valid category names to prevent typos
    VALID_CATEGORIES = {
        "state",       # Persistent state files (workflow.yaml, config.yaml)
        "agents",      # LLM agent logs per iteration
        "tools",       # Tool call logs per iteration
        "resolves",    # Resolve and check logs per iteration
        "debug",       # General debug logs
        "config"       # Configuration snapshots (if needed separately)
    }

    def __init__(self, log_root: Path, merge_name: str):
        """Initialize log manager for a merge operation.

        Args:
            log_root: Root directory containing all splintercat logs
            merge_name: Name of this merge operation (git-imerge name)
        """
        self.root = log_root / merge_name
        self.current_iteration = 0

    def set_iteration(self, iteration: int):
        """Update current iteration (called by coordinator/workflow).

        Args:
            iteration: Current resolve-check cycle number
        """
        self.current_iteration = iteration

    def _validate_category(self, category: str):
        """Validate category name.

        Args:
            category: Category to validate

        Raises:
            ValueError: If category is invalid
        """
        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid log category '{category}'. "
                f"Valid categories: {', '.join(sorted(self.VALID_CATEGORIES))}"
            )

    def get_work_dir(
        self, category: str, iteration: int | None = None
    ) -> Path:
        """Get/create work directory for any category.

        Args:
            category: Directory under default/ (e.g. 'state', 'agents')
            iteration: Iteration number for subdir (e.g. 1 -> 001/)

        Returns:
            Path to category directory (iteration subdir if specified)
        """
        self._validate_category(category)

        iter_num = iteration or self.current_iteration
        category_dir = self.root / "default" / category
        if iter_num > 0:  # Only create iteration subdir if > 0
            category_dir = category_dir / f"{iter_num:03d}"
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir

    def get_log_file(
        self, category: str, filename: str, iteration: int | None = None
    ) -> Path:
        """Get path to a log file, ensuring directory exists.

        Args:
            category: Category directory name
            filename: Filename within category (e.g. 'agent.log')
            iteration: Optional iteration for subdir

        Returns:
            Full path to log file (directory guaranteed to exist)
        """
        work_dir = self.get_work_dir(category, iteration)
        return work_dir / filename


# Unified Logger class combining logfire functionality and LogManager
class Logger:
    """
    Unified logging interface with directory management.

    Provides logfire-based logging methods plus structured
    log file management.
    """

    def __init__(self):
        self.log_manager = None

    def setup(
        self,
        min_log_level: str = 'info',
        log_root: Path | None = None,
        merge_name: str | None = None
    ):
        """Configure logging and log directory management.

        Args:
            min_log_level: Minimum log level to display
            log_root: Root directory for all log files
            merge_name: Name of this merge operation
        """
        # Set up LogManager if merge context provided
        additional_processors = []
        if log_root and merge_name:
            self.log_manager = LogManager(log_root, merge_name)
            # File logging setup deferred - done when iteration starts
            # Prevents creating files before iteration numbers set

        from logfire import ConsoleOptions

        # Configure logfire with both console and file logging
        logfire.configure(
            console=ConsoleOptions(
                min_log_level=min_log_level,
                verbose=True  # Show full span details
            ),
            additional_span_processors=(
                additional_processors if additional_processors else None
            )
        )
        # Instrument pydantic-AI for spans
        logfire.instrument_pydantic_ai()

    def enable_file_logging(self, min_log_level: str = 'info'):
        """Enable file logging for agent spans after iteration setup."""
        if self.log_manager:
            from logfire._internal.exporters.console import (
                ShowParentsConsoleSpanExporter,
            )
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            # Create agent log path with correct directory structure
            agent_log_path = self.log_manager.get_log_file(
                "agents", "agent.log"
            )

            # Configure file exporter for agent logs
            file_exporter = ShowParentsConsoleSpanExporter(
                output=open(agent_log_path, 'w', encoding='utf-8'),  # noqa: SIM115
                colors='never',  # No ANSI codes in file
                include_timestamp=True,
                include_tags=True,
                verbose=True,
                min_log_level=min_log_level
            )

            # Add the file processor to logfire
            processor = SimpleSpanProcessor(file_exporter)
            logfire.configure(
                additional_span_processors=[processor]
            )

    def set_iteration(self, iteration: int):
        """Set current iteration for log directory structure."""
        if self.log_manager:
            self.log_manager.set_iteration(iteration)

    def get_work_dir(
        self, category: str, iteration: int | None = None
    ) -> Path:
        """Get work directory for category."""
        if not self.log_manager:
            raise RuntimeError("LogManager not set - call setup() first")
        return self.log_manager.get_work_dir(category, iteration)

    def get_log_file(
        self, category: str, filename: str, iteration: int | None = None
    ) -> Path:
        """Get log file path for category and filename."""
        if not self.log_manager:
            raise RuntimeError("Call logger.setup() with log_root")
        return self.log_manager.get_log_file(category, filename, iteration)

    # Forward all other methods to logfire
    def __getattr__(self, name):
        return getattr(logfire, name)


# Create the unified logger instance
logger = Logger()
