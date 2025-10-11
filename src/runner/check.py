"""Check runner with log management."""

import os
from datetime import datetime
from pathlib import Path

from src.core.command_runner import CommandRunner
from src.core.result import CheckResult


class CheckRunner:
    """Execute check commands and manage log files."""

    def __init__(self, workdir: Path, output_dir: Path):
        """Initialize check runner.

        Args:
            workdir: Working directory for check commands
            output_dir: Directory for storing check logs
        """
        self.workdir = workdir
        self.output_dir = output_dir
        self.runner = CommandRunner()

    def run(self, check_name: str, command: str, timeout: int) -> CheckResult:
        """Run check command and save output to timestamped log file.

        Args:
            check_name: Name of check (used in log filename)
            command: Check command to execute
            timeout: Timeout in seconds

        Returns:
            CheckResult with success status, log file path, returncode, and timestamp
        """
        timestamp = datetime.now()
        log_filename = f"{check_name}-{timestamp.strftime('%Y%m%d-%H%M%S')}.log"
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
                timeout=timeout,
                log_file=log_file,
            )
        finally:
            os.chdir(original_dir)

        return CheckResult(
            check_name=check_name,
            success=(result.returncode == 0),
            log_file=log_file,
            returncode=result.returncode,
            timestamp=timestamp,
        )
