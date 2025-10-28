"""Simplified logger with composable output sinks."""

from __future__ import annotations

import contextlib
from abc import abstractmethod
from pathlib import Path
from typing import Any

from opentelemetry.proto.logs.v1 import logs_pb2
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from pydantic import Field, PrivateAttr, model_validator

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


class LevelFilteringExporter(SpanExporter):
    """Span exporter that filters spans by log level.

    Wraps another exporter and only forwards spans that meet the
    minimum level threshold.
    """

    # SINGLE SOURCE OF TRUTH: Map level names to OpenTelemetry
    # severity numbers. Used throughout for level filtering and display.
    _level_thresholds = {
        'spew': logs_pb2.SEVERITY_NUMBER_TRACE,    # 1 - most verbose
        'trace': logs_pb2.SEVERITY_NUMBER_TRACE3,  # 3
        'debug': logs_pb2.SEVERITY_NUMBER_DEBUG,   # 5
        'info': logs_pb2.SEVERITY_NUMBER_INFO,     # 9
        'warn': logs_pb2.SEVERITY_NUMBER_WARN,     # 13
        'error': logs_pb2.SEVERITY_NUMBER_ERROR,   # 17
        'fatal': logs_pb2.SEVERITY_NUMBER_FATAL,   # 21
    }

    def __init__(self, exporter: SpanExporter, min_level: str):
        """Initialize filtering exporter.

        Args:
            exporter: The underlying exporter to forward spans to
            min_level: Minimum level (spew, trace, debug, info, etc.)
        """
        self._exporter = exporter
        self._min_severity = self._level_thresholds.get(
            min_level.lower(), logs_pb2.SEVERITY_NUMBER_INFO
        )

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        """Export spans that meet the level threshold.

        OpenTelemetry severity: lower numbers = more verbose/detailed
        Higher numbers = less verbose/more important
        Filter keeps spans with severity >= min_severity
        """
        filtered = []
        for span in spans:
            attrs = span.attributes or {}
            level_num = attrs.get(
                'logfire.level_num', logs_pb2.SEVERITY_NUMBER_INFO
            )

            # Include spans at or above minimum severity
            if level_num >= self._min_severity:
                filtered.append(span)

        # Forward filtered spans to underlying exporter
        if filtered:
            return self._exporter.export(filtered)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Shutdown underlying exporter."""
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush underlying exporter."""
        return self._exporter.force_flush(timeout_millis)


class Sink(BaseConfig):
    """Base class for log output sinks.

    Each sink represents an independent output destination.
    Inherits from BaseConfig → BaseCloseable, so close() is
    automatically called during cleanup cascade.
    """

    enabled: bool = Field(default=True, description="Enable this sink")
    level: str | None = Field(
        default=None,
        description=(
            "Log level for this sink. If None, inherits from Logger.level. "
            "Valid: spew, trace, debug, info, warn, error, fatal"
        )
    )
    escape_special_characters: bool = Field(
        default=False,
        description="Escape newlines/tabs in output"
    )
    format_template: str | None = Field(
        default=None,
        description="Format template string (None for binary sinks)"
    )

    # Runtime state (not serialized)
    _processor: Any = PrivateAttr(default=None)

    @staticmethod
    def _escape_special_chars(text: str) -> str:
        """Escape special characters for single-line output."""
        return (text
            .replace('\\', '\\\\')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t')
        )

    @staticmethod
    def _extract_span_data(span) -> dict:
        """Extract common data from span for formatting."""
        from datetime import UTC, datetime

        attrs = span.attributes or {}
        ts = datetime.fromtimestamp(span.start_time / 1e9, tz=UTC)
        filepath = attrs.get("code.filepath", "")
        lineno = attrs.get("code.lineno", "")

        # Convert OpenTelemetry severity number to level name
        # Use reverse lookup from central mapping
        level_num = attrs.get(
            "logfire.level_num", logs_pb2.SEVERITY_NUMBER_INFO
        )

        # Find the level name by checking thresholds in descending order
        level_name = "unknown"
        for name in [
            'fatal', 'error', 'warn', 'info', 'debug', 'trace', 'spew'
        ]:
            threshold = LevelFilteringExporter._level_thresholds.get(name)
            if level_num >= threshold:
                level_name = name
                break

        # Calculate syslog priority (RFC 5424 severity levels)
        severity_map = {
            "spew": 7,   # Debug
            "trace": 7,  # Debug
            "debug": 7,  # Debug
            "info": 6,   # Informational
            "warn": 4,   # Warning
            "error": 3,  # Error
            "fatal": 3,  # Error
        }
        severity = severity_map.get(level_name, 6)
        priority = 8 * 1 + severity  # facility=user(1)

        return {
            'timestamp': ts,
            'level': level_name,
            'message': attrs.get("logfire.msg", span.name),
            'filepath': filepath,
            'lineno': lineno,
            'location': f"{filepath}:{lineno}" if filepath else "",
            'function': attrs.get("code.function", ""),
            'priority': priority,
        }

    def _format_span(self, span) -> str:
        """Generic span formatter using template."""
        if not self.format_template:
            # No template - use builtin JSON
            import os
            return span.to_json() + os.linesep

        # Extract data
        data = self._extract_span_data(span)

        # Escape if needed
        if self.escape_special_characters:
            data['message'] = self._escape_special_chars(data['message'])

        # Apply template
        try:
            formatted = self.format_template.format(**data)
        except KeyError as e:
            # Template references unknown field
            return f"ERROR: Invalid template field {e}\n"

        # Append custom attributes (user-provided kwargs to
        # logger calls). Skip only OpenTelemetry/instrumentation
        # internals
        attrs = span.attributes or {}
        custom_attrs = {}
        skip_prefixes = ('otel.', 'telemetry.', 'service.', 'process.')
        skip_keys = {
            'code.filepath', 'code.lineno', 'code.function',
            'logfire.msg', 'logfire.level_num', 'logfire.span_type',
            'logfire.msg_template', 'logfire.json_schema',
        }

        for key, value in attrs.items():
            # Skip internal attributes and those already in template
            if key in skip_keys:
                continue
            if any(key.startswith(prefix) for prefix in skip_prefixes):
                continue
            custom_attrs[key] = value

        # If there are custom attributes, append them
        if custom_attrs:
            attrs_str = ' '.join(
                f"{k}={repr(v)}" for k, v in sorted(custom_attrs.items())
            )
            formatted = f"{formatted} │ {attrs_str}"

        return formatted + '\n'

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

        base_exporter = OTLPSpanExporter(
            endpoint=self.endpoint,
            insecure=self.insecure,
            headers=self.headers if self.headers else None,
        )

        # Wrap with level filtering if level is set
        if self.level:
            filtered_exporter = LevelFilteringExporter(
                base_exporter, self.level
            )
            return BatchSpanProcessor(filtered_exporter)
        return BatchSpanProcessor(base_exporter)


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

        # Use generic formatter from base Sink class
        # Use ConsoleSpanExporter with custom formatter
        base_exporter = ConsoleSpanExporter(
            out=self._file,
            formatter=self._format_span
        )

        # Wrap with level filtering exporter
        filtered_exporter = LevelFilteringExporter(base_exporter, self.level)
        return BatchSpanProcessor(filtered_exporter)

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

    level: str = Field(
        default="info",
        description=(
            "Default log level for all sinks. Individual sinks can override. "
            "Valid: spew, trace, debug, info, warn, error, fatal"
        )
    )
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

    @model_validator(mode='after')
    def _cascade_level_to_sinks(self) -> 'Logger':
        """Cascade default level to sinks that don't specify their
        own."""
        for sink in [self.console, self.file]:
            if sink.level is None:
                sink.level = self.level
        return self

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
                min_log_level=self.console.level,
                verbose=self.console.verbose,
                colors=self.console.colors,
                include_timestamps=True,
            )
            if self.console.enabled
            else False
        )

        # Configure logfire with all sinks
        logfire.configure(
            service_name=f"splintercat-{merge_name}",
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
        logfire.log(
            level=LevelFilteringExporter._level_thresholds['trace'],
            msg_template=msg,
            attributes=kwargs if kwargs else None
        )

    def spew(self, msg: str, **kwargs):
        """Log very verbose spew message.

        Spew is below trace - use for extremely noisy internal
        mechanics like subprocess lifecycle events.
        """
        import logfire
        logfire.log(
            level=LevelFilteringExporter._level_thresholds['spew'],
            msg_template=msg,
            attributes=kwargs if kwargs else None
        )

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
