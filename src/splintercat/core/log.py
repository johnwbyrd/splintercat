"""Unified logging and log directory management."""

from pathlib import Path

import logfire
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter


# Category-specific logger wrapper
class CategoryLogger:
    """Logger wrapper that auto-tags all output with a category.

    Forwards all logfire methods but automatically adds category tag.
    """

    def __init__(self, category: str, parent_logger):
        """Initialize category logger.

        Args:
            category: Category name for tagging
            parent_logger: Parent Logger instance to forward calls to
        """
        self.category = category
        self.parent = parent_logger

    def __getattr__(self, name):
        """Forward logfire methods with automatic category tagging."""
        original_method = getattr(self.parent, name)

        def wrapped(*args, **kwargs):
            # Add category tag to existing tags
            tags = kwargs.get('_tags', [])
            kwargs['_tags'] = [*tags, f"category:{self.category}"]
            return original_method(*args, **kwargs)

        return wrapped


# Filtering span processor for category routing
class FilteringSpanProcessor(SpanProcessor):
    """Span processor that filters spans by category tag.

    Only exports spans tagged with the matching category.
    """

    def __init__(self, exporter: SpanExporter, category: str):
        """Initialize filtering processor.

        Args:
            exporter: The exporter to send matching spans to
            category: Export spans tagged with this category
        """
        self.exporter = exporter
        self.category = category
        self.category_tag = f"category:{category}"

    def on_start(self, span, parent_context=None):
        """Called when span starts - no filtering needed."""
        pass

    def on_end(self, span: ReadableSpan):
        """Called when span ends - filter and export if matches."""
        # Check if span has matching category tag
        # Tags are stored in 'logfire.tags' attribute
        if span.attributes:
            tags = span.attributes.get('logfire.tags', ())
            if isinstance(tags, (list, tuple)) and self.category_tag in tags:
                self.exporter.export([span])

    def shutdown(self):
        """Shutdown the exporter."""
        self.exporter.shutdown()

    def force_flush(self, timeout_millis=30000):
        """Force flush the exporter."""
        return self.exporter.force_flush(timeout_millis)


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
        "imerge",      # Git-imerge operations per iteration
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
        self.min_log_level = 'info'
        self._configured = False  # Track if already configured
        self._open_files = []  # Track open file handles for cleanup
        self._processors = []  # Track span processors for shutdown

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
        # Store min_log_level for later use in enable_file_logging
        self.min_log_level = min_log_level

        # Set up LogManager if merge context provided
        additional_processors = []
        if log_root and merge_name:
            self.log_manager = LogManager(log_root, merge_name)
            # File logging setup deferred - done when iteration starts
            # Prevents creating files before iteration numbers set

        from logfire import ConsoleOptions

        # Configure logfire with both console and file logging
        # Note: logfire.configure() can be called multiple times safely
        # Later calls will reconfigure with new settings
        logfire.configure(
            console=ConsoleOptions(
                min_log_level=min_log_level,
                verbose=True  # Show full span details
            ),
            additional_span_processors=(
                additional_processors if additional_processors else None
            )
        )

        # Instrument pydantic-AI for spans (only once)
        if not self._configured:
            logfire.instrument_pydantic_ai()
            self._configured = True

    def _create_category_exporter(self, category: str, min_log_level: str):
        """Create a file exporter for a category.

        Args:
            category: Category name
            min_log_level: Minimum log level

        Returns:
            Configured ShowParentsConsoleSpanExporter
        """
        from logfire._internal.exporters.console import (
            ShowParentsConsoleSpanExporter,
        )

        log_path = self.log_manager.get_log_file(category, f"{category}.log")
        f = open(log_path, 'w', encoding='utf-8')  # noqa: SIM115
        self._open_files.append(f)  # Track for cleanup

        return ShowParentsConsoleSpanExporter(
            output=f,
            colors='never',
            include_timestamp=True,
            include_tags=True,
            verbose=True,
            min_log_level=min_log_level
        )

    def close_files(self):
        """Close all open log files and shutdown processors."""
        for f in self._open_files:
            f.flush()
            f.close()
        self._open_files.clear()

        for p in self._processors:
            p.shutdown()
        self._processors.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: U100
        """Context manager exit - close files on ANY exit (normal or exception)."""
        self.close_files()
        return False  # Don't suppress exceptions

    def enable_file_logging(self, min_log_level: str | None = None):
        """Enable file logging with separate files per category.

        Creates a filtered log file for each category that declares
        itself via logger.for_category().

        Args:
            min_log_level: Override log level for file output
                (defaults to console level)
        """
        if self.log_manager:
            from logfire import ConsoleOptions

            file_log_level = min_log_level or self.min_log_level
            processors = []

            # Create a filtered processor for each category
            for category in self.log_manager.VALID_CATEGORIES:
                exporter = self._create_category_exporter(
                    category, file_log_level
                )
                processor = FilteringSpanProcessor(exporter, category)
                processors.append(processor)
                self._processors.append(processor)  # Track for cleanup

            # Re-configure to preserve console settings
            logfire.configure(
                console=ConsoleOptions(
                    min_log_level=self.min_log_level,
                    verbose=True
                ),
                additional_span_processors=processors
            )

    def set_iteration(self, iteration: int):
        """Set iteration and rotate log files automatically.

        Closes previous iteration's files and opens new ones.

        Args:
            iteration: Current iteration number
        """
        if self.log_manager:
            # Close previous iteration's files
            self.close_files()

            # Update iteration number
            self.log_manager.set_iteration(iteration)

            # Open new files for this iteration
            self.enable_file_logging()

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

    def for_category(self, category: str) -> CategoryLogger:
        """Get a logger that automatically tags with category.

        Args:
            category: Category name (must be in VALID_CATEGORIES)

        Returns:
            CategoryLogger that auto-tags all output
        """
        if self.log_manager:
            self.log_manager._validate_category(category)
        return CategoryLogger(category, self)

    # Forward all other methods to logfire
    def __getattr__(self, name):
        return getattr(logfire, name)


# Create the unified logger instance
logger = Logger()
