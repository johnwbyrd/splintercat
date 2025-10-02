"""Command execution with stdin support and real-time output."""


class CommandRunner:
    """Executes shell commands with optional stdin, real-time output, and interactive mode."""

    def __init__(self, interactive: bool = False):
        """Initialize CommandRunner.

        Args:
            interactive: If True, prompt before executing each command
        """
        self.interactive = interactive

    def run(self, cmd, stdin: str | None = None, check: bool = True):
        """Run a command with optional stdin.

        Args:
            cmd: Command string (uses shell) or list of args (no shell)
            stdin: Optional string to pass as stdin
            check: Whether to warn on failure

        Returns:
            Result object with returncode, stdout, stderr
        """
        raise NotImplementedError
