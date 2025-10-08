"""Command execution with stdin support and real-time output."""

import select
import subprocess
from pathlib import Path

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
        timeout: int | None = None,
        log_file: Path | None = None,
    ) -> Result:
        """Run a command with optional stdin.

        Args:
            cmd: Command string (uses shell) or list of args (no shell)
            stdin: Optional string to pass as stdin
            check: Whether to log warning on failure
            log_level: Log level for output (INFO, DEBUG, etc.)
            timeout: Optional timeout in seconds
            log_file: Optional path to save output to file

        Returns:
            Result object with returncode, stdout, stderr
        """
        if self.interactive:
            self._prompt_user(cmd, stdin)

        use_shell = isinstance(cmd, str)

        try:
            process = subprocess.Popen(
                cmd,
                shell=use_shell,
                stdin=subprocess.PIPE if stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if stdin:
                result = self._run_with_stdin(process, stdin, log_level, timeout)
            else:
                result = self._run_with_realtime_output(process, log_level, timeout)

            # Save to log file if specified
            if log_file:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "w") as f:
                    if result.stdout:
                        f.write(result.stdout)
                    if result.stderr:
                        f.write(result.stderr)

            if check and result.returncode != 0 and not self.interactive:
                logger.warning(
                    f"Command failed with return code {result.returncode}: "
                    f"{cmd if use_shell else ' '.join(cmd)}"
                )

            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout} seconds")
            process.kill()
            stdout, stderr = process.communicate()
            return Result(-1, stdout or "", stderr or "Command timed out")

    def _prompt_user(self, cmd: str | list[str], stdin: str | None):
        """Prompt user before executing command in interactive mode."""
        if isinstance(cmd, str):
            logger.info(f"Command: {cmd}")
        else:
            logger.info(f"Command: {' '.join(cmd)}")
        if stdin:
            logger.info(f"stdin: {len(stdin)} bytes")
        input("Press Enter to execute...")

    def _run_with_stdin(
        self, process: subprocess.Popen, stdin: str, log_level: str, timeout: int | None
    ) -> Result:
        """Run command with stdin, using communicate().

        Args:
            process: Running subprocess
            stdin: String to pass as stdin
            log_level: Log level for output
            timeout: Optional timeout in seconds

        Returns:
            Result object
        """
        stdout, stderr = process.communicate(input=stdin, timeout=timeout)

        # Log all output - stderr at same level as stdout since we don't know if it failed yet
        if stdout:
            for line in stdout.splitlines():
                logger.log(log_level, line)
        if stderr:
            for line in stderr.splitlines():
                logger.log(log_level, line)

        return Result(process.returncode, stdout, stderr)

    def _run_with_realtime_output(
        self, process: subprocess.Popen, log_level: str, timeout: int | None
    ) -> Result:
        """Run command with real-time output streaming.

        Uses select() to multiplex stdout/stderr in real-time.

        Args:
            process: Running subprocess
            log_level: Log level for output
            timeout: Optional timeout in seconds

        Returns:
            Result object
        """
        import time

        stdout_lines = []
        stderr_lines = []
        start_time = time.time()

        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise subprocess.TimeoutExpired(process.args, timeout)

            reads = [process.stdout.fileno(), process.stderr.fileno()]
            ready, _, _ = select.select(reads, [], [], 0.1)

            for fd in ready:
                if fd == process.stdout.fileno():
                    line = process.stdout.readline()
                    if line:
                        stdout_lines.append(line)
                        logger.log(log_level, line.rstrip())
                elif fd == process.stderr.fileno():
                    line = process.stderr.readline()
                    if line:
                        stderr_lines.append(line)
                        logger.log(log_level, line.rstrip())

            if process.poll() is not None:
                # Read any remaining output
                remaining_out = process.stdout.read()
                remaining_err = process.stderr.read()
                if remaining_out:
                    stdout_lines.append(remaining_out)
                    for line in remaining_out.splitlines():
                        logger.log(log_level, line)
                if remaining_err:
                    stderr_lines.append(remaining_err)
                    for line in remaining_err.splitlines():
                        logger.log(log_level, line)
                break

        return Result(process.returncode, "".join(stdout_lines), "".join(stderr_lines))
