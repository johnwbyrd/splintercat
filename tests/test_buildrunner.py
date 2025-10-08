"""Tests for BuildRunner."""

import tempfile
from pathlib import Path

from src.runner.build import BuildRunner


def test_successful_command():
    """Test that BuildRunner handles successful commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"
        timeout = 2

        runner = BuildRunner(workdir, output_dir, timeout)
        result = runner.run_build_test("echo 'Hello World'")

        assert result.success is True
        assert result.returncode == 0
        assert result.log_file.exists()
        assert result.timestamp is not None


def test_failed_command():
    """Test that BuildRunner handles failed commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"
        timeout = 2

        runner = BuildRunner(workdir, output_dir, timeout)
        result = runner.run_build_test("false")

        assert result.success is False
        assert result.returncode != 0
        assert result.log_file.exists()


def test_log_file_content():
    """Test that log files contain command output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"
        timeout = 2

        runner = BuildRunner(workdir, output_dir, timeout)
        result = runner.run_build_test("echo 'Test Output'")

        assert result.log_file.exists()
        content = result.log_file.read_text()
        assert "Test Output" in content


def test_timeout_handling():
    """Test that BuildRunner handles timeouts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"
        timeout = 2  # 2 second timeout

        runner = BuildRunner(workdir, output_dir, timeout)
        result = runner.run_build_test("sleep 10")

        assert result.success is False
        assert result.returncode == -1


def test_log_directory_creation():
    """Test that BuildRunner creates output directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "nonexistent" / "logs"
        timeout = 2

        assert not output_dir.exists()

        runner = BuildRunner(workdir, output_dir, timeout)
        result = runner.run_build_test("echo 'test'")

        assert output_dir.exists()
        assert result.log_file.exists()
