"""Build and test runner with log management."""

import os
from datetime import datetime
from pathlib import Path

from src.core.command_runner import CommandRunner
from src.state.build import BuildResult


class BuildRunner:
    """Execute build/test commands and manage log files."""

    def __init__(self, workdir: Path, output_dir: Path, timeout: int):
        """Initialize build runner.

        Args:
            workdir: Working directory for build commands
            output_dir: Directory for storing build logs
            timeout: Maximum time allowed for build/test in seconds
        """
        self.workdir = workdir
        self.output_dir = output_dir
        self.timeout = timeout
        self.runner = CommandRunner()

    def run_build_test(self, command: str) -> BuildResult:
        """Run build/test command and save output to timestamped log file.

        Args:
            command: Build/test command to execute

        Returns:
            BuildResult with success status, log file path, returncode, and timestamp
        """
        timestamp = datetime.now()
        log_filename = f"build-{timestamp.strftime('%Y%m%d-%H%M%S')}.log"
        log_file = self.output_dir / log_filename

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Change to workdir and run command
        original_dir = os.getcwd()
        try:
            os.chdir(str(self.workdir))
            result = self.runner.run(
                command,
                check=False,
                log_level="DEBUG",
                timeout=self.timeout,
                log_file=log_file,
            )
        finally:
            os.chdir(original_dir)

        return BuildResult(
            success=(result.returncode == 0),
            log_file=log_file,
            returncode=result.returncode,
            timestamp=timestamp,
        )
