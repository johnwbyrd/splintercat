"""Value objects for command results."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class CheckResult(BaseModel):
    """Result of a check execution."""

    check_name: str
    success: bool
    log_file: Path
    returncode: int
    timestamp: datetime


class Result:
    """Result of a command execution."""

    def __init__(self, returncode: int, stdout: str, stderr: str):
        """Initialize Result.

        Args:
            returncode: Exit code from command
            stdout: Standard output
            stderr: Standard error
        """
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def success(self) -> bool:
        """Return True if command succeeded (returncode == 0)."""
        return self.returncode == 0
