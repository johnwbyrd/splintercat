"""Test log level filtering, especially spew level."""

import tempfile
from pathlib import Path

import pytest

from splintercat.core.log import (
    ConsoleSink,
    FileSink,
    LogfireSink,
    OTLPSink,
    setup_logger,
)


@pytest.fixture
def temp_log_dir():
    """Create temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_spew_level_includes_all(temp_log_dir):
    """Test that spew level includes all messages including spew."""
    log_file = temp_log_dir / "spew.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, level="spew", path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.spew("SPEW message - should be included")
    logger.trace("TRACE message - should be included")
    logger.debug("DEBUG message - should be included")
    logger.info("INFO message - should be included")
    logger.close()

    content = log_file.read_text()

    # All levels should be included
    assert "SPEW message" in content
    assert "TRACE message" in content
    assert "DEBUG message" in content
    assert "INFO message" in content


def test_trace_level_filters_spew(temp_log_dir):
    """Test that trace level excludes spew but includes trace+."""
    log_file = temp_log_dir / "trace.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, level="trace", path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.spew("SPEW message - should be filtered")
    logger.trace("TRACE message - should be included")
    logger.debug("DEBUG message - should be included")
    logger.info("INFO message - should be included")
    logger.close()

    content = log_file.read_text()

    # Spew should be excluded
    assert "SPEW message" not in content
    # Trace and above should be included
    assert "TRACE message" in content
    assert "DEBUG message" in content
    assert "INFO message" in content


def test_debug_level_filters_trace_and_spew(temp_log_dir):
    """Test that debug level excludes trace and spew."""
    log_file = temp_log_dir / "debug.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, level="debug", path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.spew("SPEW message - should be filtered")
    logger.trace("TRACE message - should be filtered")
    logger.debug("DEBUG message - should be included")
    logger.info("INFO message - should be included")
    logger.warn("WARN message - should be included")
    logger.close()

    content = log_file.read_text()

    # Spew and trace should be excluded
    assert "SPEW message" not in content
    assert "TRACE message" not in content
    # Debug and above should be included
    assert "DEBUG message" in content
    assert "INFO message" in content
    assert "WARN message" in content


def test_info_level_filters_debug_trace_spew(temp_log_dir):
    """Test that info level excludes debug, trace, and spew."""
    log_file = temp_log_dir / "info.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, level="info", path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.spew("SPEW message - should be filtered")
    logger.trace("TRACE message - should be filtered")
    logger.debug("DEBUG message - should be filtered")
    logger.info("INFO message - should be included")
    logger.warn("WARN message - should be included")
    logger.error("ERROR message - should be included")
    logger.close()

    content = log_file.read_text()

    # Spew, trace, debug should be excluded
    assert "SPEW message" not in content
    assert "TRACE message" not in content
    assert "DEBUG message" not in content
    # Info and above should be included
    assert "INFO message" in content
    assert "WARN message" in content
    assert "ERROR message" in content


def test_warn_level_filters_below_warn(temp_log_dir):
    """Test that warn level only includes warn and above."""
    log_file = temp_log_dir / "warn.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, level="warn", path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.spew("SPEW message - should be filtered")
    logger.trace("TRACE message - should be filtered")
    logger.debug("DEBUG message - should be filtered")
    logger.info("INFO message - should be filtered")
    logger.warn("WARN message - should be included")
    logger.error("ERROR message - should be included")
    logger.close()

    content = log_file.read_text()

    # Everything below warn should be excluded
    assert "SPEW message" not in content
    assert "TRACE message" not in content
    assert "DEBUG message" not in content
    assert "INFO message" not in content
    # Warn and above should be included
    assert "WARN message" in content
    assert "ERROR message" in content


def test_error_level_only_includes_error_and_fatal(temp_log_dir):
    """Test that error level only includes error and fatal."""
    log_file = temp_log_dir / "error.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, level="error", path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.spew("SPEW message - should be filtered")
    logger.trace("TRACE message - should be filtered")
    logger.debug("DEBUG message - should be filtered")
    logger.info("INFO message - should be filtered")
    logger.warn("WARN message - should be filtered")
    logger.error("ERROR message - should be included")
    logger.close()

    content = log_file.read_text()

    # Everything below error should be excluded
    assert "SPEW message" not in content
    assert "TRACE message" not in content
    assert "DEBUG message" not in content
    assert "INFO message" not in content
    assert "WARN message" not in content
    # Error should be included
    assert "ERROR message" in content


def test_level_ordering():
    """Test level ordering: spew < trace < debug < info."""
    from splintercat.core.log import LevelFilteringExporter

    thresholds = LevelFilteringExporter._level_thresholds

    # Verify ordering: lower severity number = more verbose
    assert thresholds['spew'] < thresholds['trace']
    assert thresholds['trace'] < thresholds['debug']
    assert thresholds['debug'] < thresholds['info']
    assert thresholds['info'] < thresholds['warn']
    assert thresholds['warn'] < thresholds['error']
    assert thresholds['error'] < thresholds['fatal']

    # Verify exact values (spew=1, trace=3)
    assert thresholds['spew'] == 1  # SEVERITY_NUMBER_TRACE
    assert thresholds['trace'] == 3  # SEVERITY_NUMBER_TRACE3
    assert thresholds['debug'] == 5  # SEVERITY_NUMBER_DEBUG
    assert thresholds['info'] == 9  # SEVERITY_NUMBER_INFO
