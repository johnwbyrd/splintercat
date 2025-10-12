"""Check runner with log management."""

from datetime import datetime
from pathlib import Path

from src.core.result import CheckResult
from src.core.runner import Runner


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
        self.runner = Runner()

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

        # Run command with new Runner
        result = self.runner.execute(
            command,
            cwd=self.workdir,
            timeout=timeout,
            log_file=log_file,
            log_level="debug",
            check=False,  # Don't raise exception on failure
        )

        return CheckResult(
            check_name=check_name,
            success=(result.exited == 0),
            log_file=log_file,
            returncode=result.exited,
            timestamp=timestamp,
        )
