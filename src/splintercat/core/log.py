"""Simplified logger with composable output sinks."""

from __future__ import annotations

import contextlib
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import Field, PrivateAttr

from splintercat.core.base import BaseConfig

# Private storage for the actual logger instance
_current_logger: Logger | None = None


# Proxy object that forwards all attribute access to the current logger
class _LoggerProxy:
    """Proxy that forwards method calls to _current_logger.

    If _current_logger is None (before setup), returns no-op functions.
    If _current_logger exists, forwards all attribute access to it.
    """
    def __getattr__(self, name):
        if _current_logger is None:
            # Return no-op function before logger is initialized
            def _noop(*args, **kwargs):  # noqa: ARG001
                pass
            return _noop
        return getattr(_current_logger, name)

    def __enter__(self):
        """Support context manager protocol for spans."""
        if _current_logger is None:
            return self
        return _current_logger.__enter__()

    def __exit__(self, *args):
        """Support context manager protocol for spans."""
        if _current_logger is None:
            return False
        return _current_logger.__exit__(*args)


# Module-level logger - this is what gets imported everywhere
logger = _LoggerProxy()


class Sink(BaseConfig):
    """Base class for log output sinks.

    Each sink represents an independent output destination.
    Inherits from BaseConfig → BaseCloseable, so close() is
    automatically called during cleanup cascade.
    """

    enabled: bool = Field(default=True, description="Enable this sink")

    # Runtime state (not serialized)
    _processor: Any = PrivateAttr(default=None)

    @abstractmethod
    def create_processor(self, log_root: Path, merge_name: str):
        """Create OpenTelemetry span processor for this sink.

        Args:
            log_root: Root directory for log files
            merge_name: Current merge operation name

        Returns:
            SpanProcessor instance or None if not applicable
        """
        pass

    def close(self):
        """Close this sink - shutdown processor.

        Called automatically via BaseCloseable cleanup cascade.
        """
        if self._processor:
            with contextlib.suppress(Exception):
                self._processor.shutdown()


class ConsoleSink(Sink):
    """Console output sink (stdout/stderr)."""

    min_level: str = Field(
        default="info",
        description="Minimum log level: trace, debug, info, warn, error"
    )
    verbose: bool = Field(
        default=True,
        description="Show full span details"
    )
    colors: str = Field(
        default="auto",
        description="Color mode: auto, always, never"
    )

    def create_processor(self, log_root: Path, merge_name: str):
        """Console configured via logfire.configure()."""
        return None


class OTLPSink(Sink):
    """OTLP telemetry export sink (SigNoz, Jaeger, etc.)."""

    enabled: bool = Field(
        default=False,
        description="Enable OTLP export"
    )
    endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC endpoint"
    )
    insecure: bool = Field(
        default=True,
        description="Use insecure connection (no TLS)"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Optional headers for authentication"
    )

    def create_processor(self, log_root: Path, merge_name: str):
        """Create OTLP span exporter and processor."""
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(
            endpoint=self.endpoint,
            insecure=self.insecure,
            headers=self.headers if self.headers else None,
        )
        return BatchSpanProcessor(exporter)


class FileSink(Sink):
    """File output sink."""

    enabled: bool = Field(
        default=False,
        description="Enable file logging"
    )
    path: str = Field(
        default="{log_root}/{merge_name}/splintercat.log",
        description="Log file path template"
    )
    min_level: str = Field(
        default="debug",
        description="Minimum log level for file output"
    )

    # Runtime state
    _file: Any = PrivateAttr(default=None)

    def create_processor(self, log_root: Path, merge_name: str):
        """Create file span exporter and processor."""
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        # Expand path template
        log_path = Path(
            self.path.format(log_root=log_root, merge_name=merge_name)
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open file with line buffering (crash-safe)
        # Note: File stays open for the lifetime of the sink
        # ruff: noqa: SIM115
        self._file = open(log_path, "a", buffering=1, encoding="utf-8")  # noqa: SIM115

        # Use ConsoleSpanExporter writing to file
        exporter = ConsoleSpanExporter(out=self._file)
        return BatchSpanProcessor(exporter)

    def close(self):
        """Close processor first, then close file.

        The processor needs to flush remaining spans to the file
        before we close it.
        """
        # Close processor first (flushes remaining spans)
        super().close()

        # Then close the file
        if self._file and not self._file.closed:
            try:
                self._file.flush()
                self._file.close()
            except Exception:
                pass


class LogfireSink(Sink):
    """Logfire.dev cloud sink."""

    enabled: bool = Field(
        default=False,
        description="Send telemetry to logfire.dev cloud"
    )
    token: str | None = Field(
        default=None,
        description="API token (or use LOGFIRE_TOKEN env var)"
    )

    def create_processor(self, log_root: Path, merge_name: str):
        """Logfire configured globally via logfire.configure()."""
        return None


class Logger(BaseConfig):
    """Logger with composable output sinks.

    Because Logger inherits from BaseConfig → BaseCloseable,
    calling logger.close() automatically walks all sinks and
    calls their close() methods via the Closeable protocol.

    No manual cleanup needed - Python's context manager protocol
    ensures all resources are freed even on exceptions.
    """

    console: ConsoleSink = Field(
        default_factory=ConsoleSink,
        description="Console output configuration"
    )
    otlp: OTLPSink = Field(
        default_factory=OTLPSink,
        description="OTLP telemetry export configuration"
    )
    file: FileSink = Field(
        default_factory=FileSink,
        description="File logging configuration"
    )
    logfire: LogfireSink = Field(
        default_factory=LogfireSink,
        description="Logfire.dev cloud configuration"
    )

    def setup(self, log_root: Path, merge_name: str):
        """Initialize all enabled sinks.

        Called automatically by Config._setup_logger() validator
        after config is loaded from YAML.

        Args:
            log_root: Root directory for log files
            merge_name: Name of current merge operation
        """
        # Create processors for all enabled sinks
        for sink in [self.console, self.otlp, self.file, self.logfire]:
            if sink.enabled:
                sink._processor = sink.create_processor(log_root, merge_name)

        # Collect non-None processors
        processors = [
            sink._processor
            for sink in [self.otlp, self.file]
            if sink.enabled and sink._processor
        ]

        # Configure console
        import logfire
        from logfire import ConsoleOptions

        console_config = (
            ConsoleOptions(
                min_log_level=self.console.min_level,
                verbose=self.console.verbose,
                colors=self.console.colors,
                include_timestamps=True,
            )
            if self.console.enabled
            else False
        )

        # Configure logfire with all sinks
        logfire.configure(
            send_to_logfire=self.logfire.enabled,
            token=self.logfire.token if self.logfire.enabled else None,
            console=console_config,
            additional_span_processors=processors if processors else None,
        )

        # Instrument pydantic-ai
        logfire.instrument_pydantic_ai()

    # Logging methods - delegate to logfire

    def info(self, msg: str, **kwargs):
        """Log info message."""
        import logfire
        logfire.info(msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        import logfire
        logfire.debug(msg, **kwargs)

    def trace(self, msg: str, **kwargs):
        """Log trace message."""
        import logfire
        logfire.trace(msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        """Log warning message."""
        import logfire
        logfire.warn(msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Alias for warn()."""
        import logfire
        logfire.warn(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """Log error message."""
        import logfire
        logfire.error(msg, **kwargs)

    def span(self, msg: str, **kwargs):
        """Create a span context manager for tracing operations.

        Usage:
            with logger.span("operation_name"):
                # work here
        """
        import logfire
        return logfire.span(msg, **kwargs)

    def log(self, level: str, msg: str, **kwargs):
        """Log at specified level."""
        import logfire
        logfire.log(level, msg, **kwargs)

    def __getattr__(self, name):
        """Forward any other logfire methods."""
        import logfire
        return getattr(logfire, name)


# Module-level singleton access functions


def setup_logger(
    log_root: Path,
    merge_name: str,
    console: ConsoleSink | None = None,
    otlp: OTLPSink | None = None,
    file: FileSink | None = None,
    logfire: LogfireSink | None = None,
) -> Logger:
    """Initialize the global logger singleton.

    Called automatically by Config when loading from YAML.
    Can also be called manually for testing or standalone use.

    Args:
        log_root: Root directory for log files
        merge_name: Name of current merge operation
        console: Console sink config (or None for defaults)
        otlp: OTLP sink config (or None for defaults)
        file: File sink config (or None for defaults)
        logfire: Logfire sink config (or None for defaults)

    Returns:
        Logger: The initialized global logger instance
    """
    global _current_logger

    # Create logger with provided or default sinks
    _current_logger = Logger(
        console=console or ConsoleSink(),
        otlp=otlp or OTLPSink(),
        file=file or FileSink(),
        logfire=logfire or LogfireSink(),
    )

    # Setup all sinks
    _current_logger.setup(log_root, merge_name)

    return _current_logger
