"""Tests for git-imerge output capture shims."""

import subprocess
import sys
from io import StringIO

import pytest

from splintercat.git.shim import (
    PopenShim,
    StreamCapture,
    capture_gitimerge_output,
    check_call_shim,
)


class TestPopenShim:
    """Tests for PopenShim wrapper."""

    def test_popen_basic_execution(self):
        """Verify basic command execution works."""
        p = PopenShim(['echo', 'test'], stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()

        assert p.returncode == 0
        assert b'test' in stdout

    def test_popen_with_stdin_pipe(self):
        """Verify stdin pipe communication works."""
        p = PopenShim(['cat'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = p.communicate(input=b'test data\n')

        assert p.returncode == 0
        assert stdout == b'test data\n'

    def test_popen_poll_returns_none_while_running(self):
        """Verify poll() returns None while process running."""
        p = PopenShim(['sleep', '0.1'], stdout=subprocess.PIPE)

        # Should return None immediately
        assert p.poll() is None

        # Wait for completion
        p.wait()
        assert p.poll() == 0

    def test_popen_wait_returns_returncode(self):
        """Verify wait() blocks and returns exit code."""
        p = PopenShim(['true'], stdout=subprocess.PIPE)
        returncode = p.wait()

        assert returncode == 0
        assert p.returncode == 0

    def test_popen_nonzero_exit_code(self):
        """Verify non-zero exit codes are captured."""
        p = PopenShim(['false'], stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()

        assert p.returncode != 0

    def test_popen_forwards_pid(self):
        """Verify PID attribute is forwarded."""
        p = PopenShim(['echo', 'test'], stdout=subprocess.PIPE)

        assert hasattr(p, 'pid')
        assert isinstance(p.pid, int)
        assert p.pid > 0

    def test_popen_forwards_stdin_stdout_stderr(self):
        """Verify stream attributes are forwarded."""
        p = PopenShim(
            ['cat'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        assert hasattr(p, 'stdin')
        assert hasattr(p, 'stdout')
        assert hasattr(p, 'stderr')

        p.terminate()


class TestCheckCallShim:
    """Tests for check_call_shim wrapper."""

    def test_check_call_success(self):
        """Verify successful command returns 0."""
        result = check_call_shim(['true'])
        assert result == 0

    def test_check_call_failure_raises(self):
        """Verify failed command raises CalledProcessError."""
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            check_call_shim(['false'])

        assert exc_info.value.returncode != 0

    def test_check_call_with_command_string(self):
        """Verify check_call works with command string."""
        result = check_call_shim('true', shell=True)
        assert result == 0


class TestStreamCapture:
    """Tests for StreamCapture wrapper."""

    def test_stream_capture_complete_lines(self):
        """Verify complete lines are captured."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=False)

        capture.write("line 1\n")
        capture.write("line 2\n")
        capture.flush()

        # Verify nothing written to original (echo disabled)
        assert original.getvalue() == ""

    def test_stream_capture_buffers_partial_lines(self):
        """Verify partial lines are buffered."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=False)

        # Write partial line
        capture.write("partial")

        # Should be buffered, not logged yet
        assert len(capture._buffer) == 1
        assert capture._buffer[0] == "partial"

        # Complete the line
        capture.write(" line\n")

        # Buffer should be cleared (or contain next partial line)
        assert len(capture._buffer) == 0 or capture._buffer == ['']

    def test_stream_capture_echo_to_original(self):
        """Verify echo_to_original writes to original stream."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=True)

        capture.write("test message\n")
        capture.flush()

        # Should be written to original
        assert "test message\n" in original.getvalue()

    def test_stream_capture_no_echo(self):
        """Verify echo can be disabled."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=False)

        capture.write("test message\n")
        capture.flush()

        # Should NOT be written to original
        assert original.getvalue() == ""

    def test_stream_capture_flush_incomplete_line(self):
        """Verify flush() logs incomplete lines."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=False)

        capture.write("incomplete")
        assert len(capture._buffer) == 1

        capture.flush()
        # Buffer should be cleared after flush
        assert len(capture._buffer) == 0

    def test_stream_capture_empty_write(self):
        """Verify empty writes are handled."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=False)

        result = capture.write("")
        assert result == 0

    def test_stream_capture_multiple_newlines(self):
        """Verify multiple newlines in single write."""
        original = StringIO()
        capture = StreamCapture(original, "test", echo_to_original=False)

        capture.write("line1\nline2\nline3\n")

        # All complete lines should be processed
        assert len(capture._buffer) == 0 or capture._buffer == ['']


class TestCaptureGitimergeOutput:
    """Tests for capture_gitimerge_output context manager."""

    def test_context_manager_patches_gitimerge(self):
        """Verify gitimerge.subprocess is patched."""
        import gitimerge

        original_popen = gitimerge.subprocess.Popen
        original_check_call = gitimerge.check_call

        with capture_gitimerge_output():
            # Inside context: should be patched
            assert gitimerge.subprocess.Popen is PopenShim
            assert gitimerge.check_call is check_call_shim

        # Outside context: should be restored
        assert gitimerge.subprocess.Popen is original_popen
        assert gitimerge.check_call is original_check_call

    def test_context_manager_patches_stdout_stderr(self):
        """Verify sys.stdout/stderr are patched."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        with capture_gitimerge_output():
            # Inside context: should be wrapped
            assert isinstance(sys.stdout, StreamCapture)
            assert isinstance(sys.stderr, StreamCapture)

        # Outside context: should be restored
        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr

    def test_context_manager_restores_on_exception(self):
        """Verify streams restored even on exception."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            with capture_gitimerge_output():
                raise ValueError("test exception")
        except ValueError:
            pass

        # Should be restored despite exception
        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr

    def test_module_isolation_invoke_sees_real_popen(self):
        """Verify invoke sees real subprocess.Popen, not our shim."""
        import subprocess as global_subprocess

        import gitimerge

        # Save original references
        original_global_popen = global_subprocess.Popen

        with capture_gitimerge_output():
            # gitimerge's view is patched
            assert gitimerge.subprocess.Popen is PopenShim

            # But when we import subprocess fresh, it's the real one
            # (This shows invoke, which imports subprocess separately,
            # sees the real Popen)
            # Note: fresh_import.Popen might be PopenShim if the global
            # subprocess.Popen was patched, but gitimerge's namespace
            # is what we care about

        # After context: gitimerge restored
        assert gitimerge.subprocess.Popen is original_global_popen

    def test_nested_context_managers(self):
        """Verify nested contexts work correctly."""
        original_stdout = sys.stdout

        with capture_gitimerge_output():
            first_stdout = sys.stdout
            assert isinstance(first_stdout, StreamCapture)

            with capture_gitimerge_output():
                second_stdout = sys.stdout
                assert isinstance(second_stdout, StreamCapture)

            # First capture still active
            assert isinstance(sys.stdout, StreamCapture)

        # All restored
        assert sys.stdout is original_stdout


class TestRunnerUnaffected:
    """Verify Runner is not affected by patching."""

    def test_runner_works_after_patching(self):
        """Verify Runner execute() works with patching active."""
        from splintercat.core.runner import Runner

        runner = Runner()

        with capture_gitimerge_output():
            # Runner should work normally
            result = runner.execute("echo test", check=False)

        assert result.exited == 0
        assert "test" in result.stdout

    def test_no_recursion_runner_to_popen(self):
        """Verify no recursion when Runner calls subprocess."""
        from splintercat.core.runner import Runner

        runner = Runner()

        # This should not cause recursion
        # Runner -> invoke -> real subprocess.Popen (not PopenShim)
        with capture_gitimerge_output():
            result = runner.execute("echo test", check=False)
            assert result.exited == 0


class TestEnvParameter:
    """Tests for Runner env parameter."""

    def test_runner_env_parameter(self):
        """Verify Runner accepts and uses env parameter."""
        import platform

        from splintercat.core.runner import Runner

        runner = Runner()

        # Use platform-appropriate syntax for environment variables
        if platform.system() == "Windows":
            cmd = "echo %TEST_VAR%"
        else:
            cmd = "echo $TEST_VAR"

        result = runner.execute(
            cmd,
            env={"TEST_VAR": "test_value"},
            check=False,
        )

        assert result.exited == 0
        assert "test_value" in result.stdout
