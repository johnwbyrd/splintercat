"""Value objects for command and test results."""

from dataclasses import dataclass


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


@dataclass
class ApplyResult:
    """Result of applying a single patch.

    Attributes:
        success: True if patch applied successfully
        failed_patch_id: ID of patch that failed (None if success)
    """

    success: bool
    failed_patch_id: str | None = None
