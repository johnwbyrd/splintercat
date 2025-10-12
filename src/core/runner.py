"""Command execution using invoke library with custom extensions."""

from pathlib import Path

from invoke import Context, Result
from invoke.exceptions import CommandTimedOut

from src.core.log import logger


class Runner(Context):
    """Wrapper around invoke.Context with custom command execution methods.

    Provides custom methods that don't collide with invoke's built-in functionality.
    Uses invoke internally for all command execution.
    """

    def execute(
        self,
        command: str,
        cwd: Path | None = None,
        timeout: int | None = None,
        stdin: str | None = None,
        log_file: Path | None = None,
        log_level: str | None = None,
        check: bool = True,
    ) -> Result:
        """Execute a command with full control over execution parameters.

        Args:
            command: Command string to execute
            cwd: Working directory for command execution
            timeout: Maximum execution time in seconds
            stdin: String to send to command's stdin
            log_file: Path to write combined stdout/stderr output
            log_level: Log level for real-time output (INFO, DEBUG, etc.)
            check: If True, raise exception on non-zero exit code

        Returns:
            invoke.Result with stdout, stderr, exited (return code)

        Raises:
            invoke.UnexpectedExit: If check=True and command returns non-zero
        """
        # Prepare invoke kwargs
        kwargs = {
            "hide": True,  # Capture output, don't print to console
            "warn": not check,  # If check=False, don't raise on error
            "in_stream": False,  # Don't read from stdin by default
        }

        if timeout:
            kwargs["timeout"] = timeout

        if stdin:
            kwargs["in_stream"] = stdin

        # Execute with or without cwd, catching timeout exceptions
        try:
            if cwd:
                with self.cd(str(cwd)):
                    result = self.run(command, **kwargs)
            else:
                result = self.run(command, **kwargs)
        except CommandTimedOut as e:
            # Convert timeout exception to result with returncode -1
            # This matches the old CommandRunner behavior
            result = e.result
            result.exited = -1

        # Write to log file if requested
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            combined = result.stdout + result.stderr
            log_file.write_text(combined)

        # Real-time logging if requested
        if log_level:
            for line in result.stdout.splitlines():
                logger.log(log_level, line.rstrip())
            for line in result.stderr.splitlines():
                logger.log(log_level, line.rstrip())

        return result
