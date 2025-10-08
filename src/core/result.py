"""Value objects for command results."""


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
