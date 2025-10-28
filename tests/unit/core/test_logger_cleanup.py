"""Tests for logger cleanup cascade via BaseCloseable."""


import pytest

from splintercat.core.log import ConsoleSink, FileSink, Logger, OTLPSink


def test_logger_closes_file_via_context_manager(tmp_path):
    """Test that logger closes files when used as context manager."""
    logger = Logger(
        console=ConsoleSink(enabled=False),
        file=FileSink(enabled=True, path=str(tmp_path / "test.log")),
        otlp=OTLPSink(enabled=False),
        logfire={"enabled": False}
    )

    logger.setup(log_root=tmp_path, merge_name="test")

    # File should be open after setup
    assert logger.file._file is not None
    assert not logger.file._file.closed

    # Use context manager
    with logger:
        logger.info("test message")

    # File should be closed after context exit
    assert logger.file._file.closed


def test_logger_closes_on_exception(tmp_path):
    """Test that logger closes files even when exception occurs."""
    logger = Logger(
        console=ConsoleSink(enabled=False),
        file=FileSink(enabled=True, path=str(tmp_path / "test.log")),
        otlp=OTLPSink(enabled=False),
        logfire={"enabled": False}
    )

    logger.setup(log_root=tmp_path, merge_name="test")

    # Raise exception inside context
    with pytest.raises(ValueError), logger:
        logger.info("before exception")
        raise ValueError("test exception")

    # File should still be closed despite exception
    assert logger.file._file.closed


def test_config_cascade_closes_logger(tmp_path):
    """Test Config.close() cascades to Logger then Sink.close()."""
    from splintercat.core.config import (
        CheckConfig,
        Config,
        GitConfig,
        LLMConfig,
    )
    from splintercat.core.log import Logger

    # Create config with logger
    config = Config(
        logger=Logger(
            console=ConsoleSink(enabled=False),
            file=FileSink(enabled=True, path=str(tmp_path / "cascade.log")),
            otlp=OTLPSink(enabled=False),
            logfire={"enabled": False}
        ),
        git=GitConfig(
            source_ref="test-ref",
            target_workdir=tmp_path,
            target_branch="main",
            imerge_name="test-merge"
        ),
        check=CheckConfig(
            output_dir=tmp_path / "checks",
            commands={"quick": "echo test"}
        ),
        llm=LLMConfig(model="openai:gpt-4")
    )

    # Setup logger (normally done by validator, bypassing here)
    config.logger.setup(log_root=tmp_path, merge_name="test-merge")

    # File should be open
    assert config.logger.file._file is not None
    assert not config.logger.file._file.closed

    # Close config - should cascade through logger to sinks
    config.close()

    # File should be closed via cascade
    assert config.logger.file._file.closed


def test_multiple_sinks_all_close(tmp_path):
    """Test that all enabled sinks are closed."""
    logger = Logger(
        console=ConsoleSink(enabled=True),  # No file handle, should not error
        file=FileSink(enabled=True, path=str(tmp_path / "multi.log")),
        otlp=OTLPSink(enabled=False),
        logfire={"enabled": False}
    )

    logger.setup(log_root=tmp_path, merge_name="multi-test")

    # File should be open
    assert logger.file._file is not None
    assert not logger.file._file.closed

    # Close logger
    logger.close()

    # All sinks should be closed
    assert logger.file._file.closed
    # Console sink has no resources to close, should not error
    # OTLP is disabled, should not error


def test_file_written_and_flushed_on_close(tmp_path):
    """Test that log file is written and flushed on close."""
    from splintercat.core.log import LogfireSink

    log_file = tmp_path / "written.log"

    logger = Logger(
        console=ConsoleSink(enabled=False),
        file=FileSink(enabled=True, path=str(log_file)),
        otlp=OTLPSink(enabled=False),
        logfire=LogfireSink(enabled=False)
    )

    logger.setup(log_root=tmp_path, merge_name="write-test")

    with logger:
        logger.info("test message to file")

    # File should exist and contain message
    assert log_file.exists()
    content = log_file.read_text()
    assert "test message to file" in content
