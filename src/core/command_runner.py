"""Command execution with stdin support and real-time output."""

import select
import subprocess

from src.core.log import logger
from src.core.result import Result


class CommandRunner:
    """Executes shell commands with optional stdin, real-time output, and interactive mode."""

    def __init__(self, interactive: bool = False):
        """Initialize CommandRunner.

        Args:
            interactive: If True, prompt before executing each command
        """
        self.interactive = interactive

    def run(
        self,
        cmd: str | list[str],
        stdin: str | None = None,
        check: bool = True,
        log_level: str = "INFO",
    ) -> Result:
        """Run a command with optional stdin.

        Args:
            cmd: Command string (uses shell) or list of args (no shell)
            stdin: Optional string to pass as stdin
            check: Whether to log warning on failure
            log_level: Log level for output (INFO, DEBUG, etc.)

        Returns:
            Result object with returncode, stdout, stderr
        """
        if self.interactive:
            self._prompt_user(cmd, stdin)

        use_shell = isinstance(cmd, str)

        process = subprocess.Popen(
            cmd,
            shell=use_shell,
            stdin=subprocess.PIPE if stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if stdin:
            result = self._run_with_stdin(process, stdin, log_level)
        else:
            result = self._run_with_realtime_output(process, log_level)

        if check and result.returncode != 0 and not self.interactive:
            logger.warning(
                f"Command failed with return code {result.returncode}: "
                f"{cmd if use_shell else ' '.join(cmd)}"
            )

        return result

    def _prompt_user(self, cmd: str | list[str], stdin: str | None):
        """Prompt user before executing command in interactive mode."""
        if isinstance(cmd, str):
            logger.info(f"Command: {cmd}")
        else:
            logger.info(f"Command: {' '.join(cmd)}")
        if stdin:
            logger.info(f"stdin: {len(stdin)} bytes")
        input("Press Enter to execute...")

    def _run_with_stdin(self, process: subprocess.Popen, stdin: str) -> Result:
        """Run command with stdin, using communicate().

        Args:
            process: Running subprocess
            stdin: String to pass as stdin

        Returns:
            Result object
        """
        stdout, stderr = process.communicate(input=stdin)

        # Log all output
        if stdout:
            for line in stdout.splitlines():
                logger.info(line)
        if stderr:
            for line in stderr.splitlines():
                logger.error(line)

        return Result(process.returncode, stdout, stderr)

    def _run_with_realtime_output(self, process: subprocess.Popen) -> Result:
        """Run command with real-time output streaming.

        Uses select() to multiplex stdout/stderr in real-time.

        Args:
            process: Running subprocess

        Returns:
            Result object
        """
        stdout_lines = []
        stderr_lines = []

        while True:
            reads = [process.stdout.fileno(), process.stderr.fileno()]
            ready, _, _ = select.select(reads, [], [], 0.1)

            for fd in ready:
                if fd == process.stdout.fileno():
                    line = process.stdout.readline()
                    if line:
                        stdout_lines.append(line)
                        logger.info(line.rstrip())
                elif fd == process.stderr.fileno():
                    line = process.stderr.readline()
                    if line:
                        stderr_lines.append(line)
                        logger.error(line.rstrip())

            if process.poll() is not None:
                # Read any remaining output
                remaining_out = process.stdout.read()
                remaining_err = process.stderr.read()
                if remaining_out:
                    stdout_lines.append(remaining_out)
                    for line in remaining_out.splitlines():
                        logger.info(line)
                if remaining_err:
                    stderr_lines.append(remaining_err)
                    for line in remaining_err.splitlines():
                        logger.error(line)
                break

        return Result(process.returncode, "".join(stdout_lines), "".join(stderr_lines))
