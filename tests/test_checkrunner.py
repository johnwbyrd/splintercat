"""Tests for CheckRunner."""

import tempfile
from pathlib import Path

from src.runner.check import CheckRunner


def test_successful_command():
    """Test that CheckRunner handles successful commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"

        runner = CheckRunner(workdir, output_dir)
        result = runner.run("quick", "echo 'Hello World'", timeout=2)

        assert result.success is True
        assert result.returncode == 0
        assert result.log_file.exists()
        assert result.timestamp is not None
        assert result.check_name == "quick"


def test_failed_command():
    """Test that CheckRunner handles failed commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"

        runner = CheckRunner(workdir, output_dir)
        result = runner.run("normal", "false", timeout=2)

        assert result.success is False
        assert result.returncode != 0
        assert result.log_file.exists()
        assert result.check_name == "normal"


def test_log_file_content():
    """Test that log files contain command output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"

        runner = CheckRunner(workdir, output_dir)
        result = runner.run("test", "echo 'Test Output'", timeout=2)

        assert result.log_file.exists()
        content = result.log_file.read_text()
        assert "Test Output" in content


def test_timeout_handling():
    """Test that CheckRunner handles timeouts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"

        runner = CheckRunner(workdir, output_dir)
        result = runner.run("slow", "sleep 10", timeout=2)

        assert result.success is False
        assert result.returncode == -1


def test_log_directory_creation():
    """Test that CheckRunner creates output directory if it
    doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "nonexistent" / "logs"

        assert not output_dir.exists()

        runner = CheckRunner(workdir, output_dir)
        result = runner.run("test", "echo 'test'", timeout=2)

        assert output_dir.exists()
        assert result.log_file.exists()


def test_check_name_in_log_filename():
    """Test that check name appears in log filename."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        output_dir = Path(tmpdir) / "logs"

        runner = CheckRunner(workdir, output_dir)
        result = runner.run("mycheck", "echo 'test'", timeout=2)

        assert "mycheck" in result.log_file.name
