"""Test log format templates."""

import re
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


def test_default_json_format(temp_log_dir):
    """Test that default (no template) produces JSON output."""
    log_file = temp_log_dir / "default.log"

    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(enabled=True, path=str(log_file)),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Test message")
    logger.close()

    content = log_file.read_text()
    # Default (no template) should be JSON (OpenTelemetry span format)
    assert content.startswith("{")
    assert '"name": "Test message"' in content
    assert '"context"' in content


def test_text_format(temp_log_dir):
    """Test text format template produces correct output."""
    log_file = temp_log_dir / "text.log"

    template = (
        "{timestamp:%Y-%m-%d %H:%M:%S.%f} "
        "[{level}] {location} {message}"
    )
    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(
            enabled=True,
            path=str(log_file),
            format_template=template
        ),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Test message")
    logger.close()

    content = log_file.read_text()
    line = content.strip()

    # Expected: 2025-10-26 11:12:03.621747 [info]
    # src/splintercat/core/log.py:393 Test message
    # Validate structure with regex
    pattern = (
        r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ '
        r'\[(trace|debug|info|notice|warn|warning|error|fatal)\] '
        r'.+\.py:\d+ Test message$'
    )
    assert re.match(pattern, line), (
        f"Text format doesn't match expected pattern. Got: {line}"
    )

    # Verify key components
    assert "[" in line and "]" in line  # Level in brackets
    assert ".py:" in line  # Filepath:lineno
    assert "Test message" in line


def test_logfmt_format(temp_log_dir):
    """Test logfmt format produces correct key=value output."""
    log_file = temp_log_dir / "logfmt.log"

    template = (
        'time={timestamp:%Y-%m-%dT%H:%M:%S%z} level={level} '
        'file={filepath} line={lineno} msg="{message}"'
    )
    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(
            enabled=True,
            path=str(log_file),
            format_template=template
        ),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Test message")
    logger.close()

    content = log_file.read_text()
    line = content.strip()

    # Expected: time=2025-10-26T11:12:03+0000 level=INFO
    # file=src/splintercat/core/log.py line=393 msg="Test message"
    assert "time=" in line
    assert re.search(
        r'time=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}',
        line
    )
    assert "level=" in line
    assert "file=" in line
    assert ".py" in line
    assert "line=" in line
    assert re.search(r'line=\d+', line)
    assert 'msg="Test message"' in line


def test_clf_format(temp_log_dir):
    """Test Common Log Format produces correct output."""
    log_file = temp_log_dir / "clf.log"

    template = (
        '- - - [{timestamp:%d/%b/%Y:%H:%M:%S %z}] '
        '"{level} {location}" - - "{message}"'
    )
    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(
            enabled=True,
            path=str(log_file),
            format_template=template
        ),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Test message")
    logger.close()

    content = log_file.read_text()
    line = content.strip()

    # Expected: - - - [26/Oct/2025:11:12:03 +0000]
    # "INFO src/splintercat/core/log.py:393" - - "Test message"
    assert line.startswith("- - - [")
    assert re.search(
        r'\[\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}\]',
        line
    )
    assert ".py:" in line
    assert '"Test message"' in line


def test_syslog_format(temp_log_dir):
    """Test RFC 5424 syslog format produces correct output."""
    log_file = temp_log_dir / "syslog.log"

    template = (
        "<{priority}>1 {timestamp:%Y-%m-%dT%H:%M:%S%z} - "
        "splintercat - - - {message}"
    )
    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(
            enabled=True,
            path=str(log_file),
            format_template=template
        ),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Test message")
    logger.close()

    content = log_file.read_text()
    line = content.strip()

    # Expected: <14>1 2025-10-26T11:12:03+0000 - splintercat
    # - - - Test message
    pattern = (
        r'^<\d+>1 \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4} '
        r'- splintercat - - - Test message$'
    )
    assert re.match(pattern, line), (
        f"Syslog format doesn't match expected pattern. Got: {line}"
    )
    assert line.startswith("<")
    assert ">1 " in line
    assert "splintercat" in line
    assert "Test message" in line


def test_escape_special_characters(temp_log_dir):
    """Test escape_special_characters escapes newlines and tabs."""
    log_file = temp_log_dir / "escaped.log"

    template = "{message}"
    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(
            enabled=True,
            path=str(log_file),
            format_template=template,
            escape_special_characters=True
        ),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Line 1\nLine 2\tTabbed")
    logger.close()

    content = log_file.read_text()

    # Should be: 'Line 1\\nLine 2\\tTabbed\n'
    expected = 'Line 1\\nLine 2\\tTabbed\n'
    assert content == expected, (
        f"Expected escaped output, got: {repr(content)}"
    )
    assert "\\n" in content  # Escaped newline
    assert "\\t" in content  # Escaped tab
    assert content.count("\n") == 1  # Only the final newline is real


def test_no_escape_special_characters(temp_log_dir):
    """Test that special characters are NOT escaped by default."""
    log_file = temp_log_dir / "not_escaped.log"

    template = "{message}"
    logger = setup_logger(
        log_root=temp_log_dir,
        merge_name="test",
        console=ConsoleSink(enabled=False),
        otlp=OTLPSink(enabled=False),
        file=FileSink(
            enabled=True,
            path=str(log_file),
            format_template=template,
            escape_special_characters=False
        ),
        logfire=LogfireSink(enabled=False),
    )

    logger.info("Line 1\nLine 2\tTabbed")
    logger.close()

    content = log_file.read_text()

    # Should be: 'Line 1\nLine 2\tTabbed\n'
    expected = 'Line 1\nLine 2\tTabbed\n'
    assert content == expected, (
        f"Expected unescaped output, got: {repr(content)}"
    )
    assert "\\n" not in content  # No escaped newlines
    assert "\\t" not in content  # No escaped tabs
    # Two real newlines (within message + final)
    assert content.count("\n") == 2
