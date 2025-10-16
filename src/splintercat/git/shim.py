"""Output capture shims for git-imerge.

This module provides transparent wrappers that capture and log all output
from git-imerge operations through three mechanisms:

1. subprocess.Popen wrapper - Logs all git command executions
2. subprocess.check_call wrapper - Logs check_call operations
3. sys.stdout/stderr wrappers - Captures progress messages

All output is routed through logfire for complete observability while
maintaining normal terminal output (configurable).
"""

import sys
from contextlib import contextmanager
from io import TextIOBase

from splintercat.core.log import logger

# Import subprocess and IMMEDIATELY save the real Popen before any patching
import subprocess
_REAL_POPEN = subprocess.Popen
_REAL_CHECK_CALL = subprocess.check_call


class PopenShim:
    """Transparent wrapper around subprocess.Popen with logging.

    This wrapper:
    - Logs command execution details via logfire
    - Creates a real subprocess.Popen for actual work
    - Forwards all method calls and attribute access
    - Logs completion events and return codes
    - Has zero functional differences from real Popen

    Example:
        >>> p = PopenShim(['echo', 'test'], stdout=subprocess.PIPE)
        >>> stdout, stderr = p.communicate()
        >>> print(p.returncode)
        0
    """

    def __init__(self, args, **kwargs):
        """Create Popen with command logging.

        Args:
            args: Command and arguments (list or string)
            **kwargs: All subprocess.Popen keyword arguments
        """
        # Format command for logging
        if isinstance(args, list):
            cmd_str = ' '.join(str(arg) for arg in args)
        else:
            cmd_str = str(args)

        cwd = kwargs.get('cwd')
        stdin_mode = kwargs.get('stdin')
        stdout_mode = kwargs.get('stdout')
        stderr_mode = kwargs.get('stderr')

        # Determine if using pipes
        uses_stdin = stdin_mode == subprocess.PIPE
        uses_stdout = stdout_mode == subprocess.PIPE
        uses_stderr = stderr_mode == subprocess.PIPE

        # Log command start
        logger.debug(
            "git-imerge subprocess",
            command=cmd_str,
            cwd=str(cwd) if cwd else None,
            uses_stdin_pipe=uses_stdin,
            uses_stdout_pipe=uses_stdout,
            uses_stderr_pipe=uses_stderr,
        )

        # Create REAL subprocess.Popen
        # Note: Uses _REAL_POPEN saved at module import time
        self._process = _REAL_POPEN(args, **kwargs)

        logger.debug(f"Started process PID {self._process.pid}")

    def communicate(self, input=None, timeout=None):
        """Send input and wait for completion.

        Args:
            input: Data to send to stdin (bytes or None)
            timeout: Timeout in seconds (optional)

        Returns:
            Tuple of (stdout, stderr) as bytes
        """
        stdout, stderr = self._process.communicate(input, timeout)

        # Log completion
        logger.debug(
            "Process communicate() completed",
            returncode=self._process.returncode,
            stdout_bytes=len(stdout) if stdout else 0,
            stderr_bytes=len(stderr) if stderr else 0,
        )

        return (stdout, stderr)

    def poll(self):
        """Check if process has terminated.

        Returns:
            Return code if terminated, None otherwise
        """
        returncode = self._process.poll()

        # Log first time we see completion
        if returncode is not None and not hasattr(self, '_poll_logged'):
            logger.debug(f"Process exited with code {returncode}")
            self._poll_logged = True

        return returncode

    def wait(self, timeout=None):
        """Wait for process to terminate.

        Args:
            timeout: Timeout in seconds (optional)

        Returns:
            Return code
        """
        returncode = self._process.wait(timeout)
        logger.debug(f"Process wait() returned code {returncode}")
        return returncode

    def __enter__(self):
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support context manager protocol."""
        if self._process.stdout:
            self._process.stdout.close()
        if self._process.stderr:
            self._process.stderr.close()
        if self._process.stdin:
            self._process.stdin.close()
        self._process.wait()
        return False

    def __getattr__(self, name):
        """Forward all other attributes to real process.

        This makes PopenShim a transparent proxy - any attribute
        not explicitly defined above (like stdin, stdout, stderr,
        pid, terminate, kill, etc.) is forwarded to the real process.

        Args:
            name: Attribute name

        Returns:
            Attribute value from real process
        """
        return getattr(self._process, name)


def check_call_shim(*args, **kwargs):
    """Wrapper for subprocess.check_call with logging.

    Logs the command being executed and whether it succeeded or failed,
    then delegates to real subprocess.check_call.

    Args:
        *args: Positional arguments for check_call
        **kwargs: Keyword arguments for check_call

    Returns:
        0 (on success)

    Raises:
        CalledProcessError: If command returns non-zero exit code
    """
    # Format command for logging
    if isinstance(args[0], list):
        cmd_str = ' '.join(str(arg) for arg in args[0])
    else:
        cmd_str = str(args[0])

    cwd = kwargs.get('cwd')

    # Log command execution
    logger.debug(
        "git-imerge check_call",
        command=cmd_str,
        cwd=str(cwd) if cwd else None,
    )

    try:
        result = _REAL_CHECK_CALL(*args, **kwargs)
        logger.debug("check_call succeeded")
        return result
    except subprocess.CalledProcessError as e:
        logger.debug(f"check_call failed with code {e.returncode}")
        raise


class StreamCapture(TextIOBase):
    """Wrapper for sys.stdout/stderr that logs writes to logfire.

    This wrapper:
    - Buffers partial lines for cleaner logging
    - Logs complete lines via logfire
    - Optionally echoes to original stream (for terminal visibility)
    - Maintains full TextIOBase compatibility

    Example:
        >>> original = sys.stdout
        >>> sys.stdout = StreamCapture(original, "stdout")
        >>> print("test")  # Logged and printed
        test
    """

    def __init__(
        self,
        original_stream,
        stream_name: str,
        echo_to_original: bool = True
    ):
        """Initialize stream wrapper.

        Args:
            original_stream: The real sys.stdout or sys.stderr
            stream_name: "stdout" or "stderr" (for logging context)
            echo_to_original: If True, also write to original stream
        """
        super().__init__()
        self.original_stream = original_stream
        self.stream_name = stream_name
        self.echo_to_original = echo_to_original
        self._buffer = []  # Buffer for incomplete lines

    def write(self, text: str) -> int:
        """Write text, logging complete lines.

        Buffers partial lines until a newline is encountered.
        git-imerge often writes "Attempting..." then later "success.\n"
        so buffering prevents logging incomplete messages.

        Args:
            text: String to write

        Returns:
            Number of characters written
        """
        if not text:
            return 0

        # Add to buffer
        self._buffer.append(text)

        # If we have newlines, flush complete lines
        if '\n' in text:
            complete = ''.join(self._buffer)
            lines = complete.split('\n')

            # Log all complete lines
            for line in lines[:-1]:
                if line:  # Skip empty lines
                    logger.info(
                        f"git-imerge {self.stream_name}",
                        message=line,
                    )

            # Keep incomplete last line in buffer
            self._buffer = [lines[-1]] if lines[-1] else []

        # Echo to original stream if requested
        if self.echo_to_original:
            self.original_stream.write(text)
            self.original_stream.flush()

        return len(text)

    def flush(self):
        """Flush buffered content.

        Logs any incomplete line remaining in buffer and flushes
        the original stream.
        """
        # Flush any incomplete line
        if self._buffer:
            incomplete = ''.join(self._buffer)
            if incomplete:
                logger.info(
                    f"git-imerge {self.stream_name}",
                    message=incomplete,
                    incomplete=True,
                )
            self._buffer = []

        if self.echo_to_original:
            self.original_stream.flush()

    def __getattr__(self, name):
        """Forward all other operations to original stream.

        Args:
            name: Attribute name

        Returns:
            Attribute value from original stream
        """
        return getattr(self.original_stream, name)


@contextmanager
def capture_gitimerge_output(echo_to_terminal: bool = False):
    """Context manager that captures all git-imerge output.

    Patches three things:
    1. gitimerge.subprocess.Popen -> PopenShim
    2. gitimerge.check_call -> check_call_shim
    3. sys.stdout/stderr -> StreamCapture

    All patches are restored on exit, even if an exception occurs.

    Args:
        echo_to_terminal: If True, output still appears in terminal

    Yields:
        None

    Example:
        >>> with capture_gitimerge_output():
        ...     imerge = gitimerge.MergeState.initialize(...)
        ...     # All subprocess calls and output logged
    """
    import gitimerge

    # Save originals
    original_popen = gitimerge.subprocess.Popen
    original_check_call = gitimerge.check_call
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        # Patch subprocess in gitimerge's namespace
        # Note: This only affects gitimerge's view of subprocess
        # Global subprocess.Popen and invoke's view are unchanged
        gitimerge.subprocess.Popen = PopenShim
        gitimerge.check_call = check_call_shim

        # Patch stdout/stderr globally
        # Note: This affects all code, but scope is narrow (just this context)
        sys.stdout = StreamCapture(original_stdout, "stdout", echo_to_terminal)
        sys.stderr = StreamCapture(original_stderr, "stderr", echo_to_terminal)

        logger.info(
            "git-imerge output capture enabled",
            subprocess_patched=True,
            stdout_captured=True,
            stderr_captured=True,
        )

        yield

    finally:
        # Restore everything
        gitimerge.subprocess.Popen = original_popen
        gitimerge.check_call = original_check_call
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        logger.debug("git-imerge output capture disabled")
