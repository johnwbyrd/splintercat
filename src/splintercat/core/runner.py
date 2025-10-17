"""Command execution using invoke library with custom extensions."""

import contextlib
import os
from pathlib import Path

from invoke import Context, Result
from invoke.exceptions import CommandTimedOut

from splintercat.core.log import logger


class Runner(Context):
    """Wrapper around invoke.Context with custom command
    execution methods.

    Provides custom methods that don't collide with invoke's
    built-in functionality. Uses invoke internally for all
    command execution.
    """

    def kill(self) -> None:
        """Kill the running subprocess.

        This overrides invoke.Context.kill() to work around a bug
        where invoke tries to use signal.SIGKILL on Windows, which
        doesn't exist. Windows doesn't support POSIX signals - the
        signal module only defines CTRL_C_EVENT, CTRL_BREAK_EVENT,
        and a few others (SIGABRT, SIGFPE, SIGILL, SIGINT, SIGSEGV,
        SIGTERM).

        The invoke library's kill() method (invoke/runners.py:1350)
        calls:
            os.kill(pid, signal.SIGKILL)

        On Windows, this raises:
            AttributeError: module 'signal' has no attribute
            'SIGKILL'

        However, os.kill() on Windows accepts numeric values and
        passes them to TerminateProcess() as exit codes. We use
        numeric value 9 (SIGKILL's value on Unix) which works
        correctly on Windows.

        On POSIX systems (Linux, macOS, BSD), delegate to invoke's
        original implementation which works fine.

        Bug discovered via Windows CI test failures in
        test_checkrunner.py test_timeout_handling, which triggers
        timeout cleanup.

        References:
        - https://bugs.python.org/issue1220212 (os.kill on Windows)
        - https://bugs.python.org/issue26350 (signal/os.kill
          Windows docs)
        - https://github.com/pyinvoke/invoke/blob/main/invoke/
          runners.py#L1350
        """
        import platform

        if platform.system() == "Windows":
            # Windows doesn't have signal.SIGKILL, use numeric value
            pid = self.pid if self.using_pty else self.process.pid
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, 9)  # SIGKILL = 9 on Unix, works on Win
            return

        # On POSIX, use invoke's original implementation
        super().kill()

    def execute(
        self,
        command: str,
        cwd: Path | None = None,
        timeout: int | None = None,
        stdin: str | None = None,
        log_file: Path | None = None,
        log_level: str | None = None,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> Result:
        """Execute a command with full control over execution
        parameters.

        Args:
            command: Command string to execute
            cwd: Working directory for command execution
            timeout: Maximum execution time in seconds
            stdin: String to send to command's stdin
            log_file: Path to write combined stdout/stderr output
            log_level: Log level for real-time output
                (INFO, DEBUG, etc.)
            check: If True, raise exception on non-zero exit
                code
            env: Environment variables to set (updates os.environ,
                does not replace it)

        Returns:
            invoke.Result with stdout, stderr, exited (return
                code)

        Raises:
            invoke.UnexpectedExit: If check=True and command
                returns non-zero
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

        if env:
            kwargs["env"] = env

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
