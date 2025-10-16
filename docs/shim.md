# git-imerge Output Capture Implementation

## Overview

This document specifies the complete implementation for capturing and logging all git-imerge output. The goal is comprehensive observability: every subprocess call, every progress message, every output must flow through logfire for tracking and debugging.

## Problem Statement

git-imerge produces output through three channels:
1. **subprocess.Popen** - 8 direct calls for git commands
2. **subprocess.check_call** - 18 calls (imported from subprocess module)
3. **sys.stderr.write()** - 38 progress messages like "Attempting to merge 1-1..."
4. **sys.stdout.write()** - List output and status information

All three channels must be captured without:
- Breaking git-imerge functionality
- Affecting other code (invoke, Runner, other libraries)
- Creating recursion or circular dependencies
- Losing any output

## Architecture

### File Organization

**Single file for all shims:** `src/splintercat/git/shim.py`

This file contains:
- `PopenShim` class - subprocess.Popen wrapper
- `check_call_shim` function - subprocess.check_call wrapper
- `StreamCapture` class - sys.stdout/stderr wrapper
- `capture_gitimerge_output()` context manager - orchestrates all three
- Module-level helpers for patching/restoration

**Modified file:** `src/splintercat/git/imerge.py`

Uses the context manager to wrap all gitimerge operations.

**Modified file:** `src/splintercat/core/runner.py`

Add `env` parameter for completeness (minor enhancement).

### Responsibility Separation

#### shim.py Responsibilities
- Wrap subprocess.Popen with logging
- Wrap subprocess.check_call with logging
- Wrap sys.stdout/stderr with logging
- Provide context manager for enabling/disabling capture
- Patch ONLY gitimerge's namespace (not global subprocess)
- Restore everything on exit

#### imerge.py Responsibilities
- Use context manager around gitimerge operations
- Provide clean Python API for git-imerge
- Handle working directory management
- No direct knowledge of patching internals

#### runner.py Responsibilities
- Execute commands via invoke
- Support environment variable passing
- No knowledge of git-imerge or patching

## Detailed Implementation

### Class: PopenShim

**Purpose:** Transparent wrapper for subprocess.Popen that logs all operations.

**Location:** `src/splintercat/git/shim.py`

**Interface:**
```python
class PopenShim:
    """Transparent wrapper around subprocess.Popen with logging.

    Creates a real subprocess.Popen and forwards all operations.
    Logs command execution and completion via logfire.
    """

    def __init__(self, args, **kwargs):
        """Log command and create real Popen."""

    def communicate(self, input=None, timeout=None) -> tuple[bytes, bytes]:
        """Forward to real process, log completion."""

    def poll(self) -> int | None:
        """Forward to real process."""

    def wait(self, timeout=None) -> int:
        """Forward to real process, log completion."""

    def __getattr__(self, name):
        """Forward all other attributes to real process."""
```

**Key behaviors:**
- Never reimplements I/O - always delegates to real subprocess.Popen
- Logs before creating process (command, cwd, PID)
- Logs after completion (returncode, output sizes)
- Zero functional differences from real Popen

**Implementation details:**
```python
import subprocess as real_subprocess
from splintercat.core.log import logger

class PopenShim:
    def __init__(self, args, **kwargs):
        # Format command for logging
        if isinstance(args, list):
            cmd_str = ' '.join(str(arg) for arg in args)
        else:
            cmd_str = str(args)

        cwd = kwargs.get('cwd')

        # Log command start
        with logger.span("git-imerge subprocess", command=cmd_str, cwd=cwd):
            # Create REAL subprocess.Popen (not recursive - uses real_subprocess)
            self._process = real_subprocess.Popen(args, **kwargs)
            logger.debug(f"Started process PID {self._process.pid}")

    def communicate(self, input=None, timeout=None):
        stdout, stderr = self._process.communicate(input, timeout)
        logger.debug(
            "Process completed",
            returncode=self._process.returncode,
            stdout_bytes=len(stdout) if stdout else 0,
            stderr_bytes=len(stderr) if stderr else 0
        )
        return (stdout, stderr)

    def poll(self):
        returncode = self._process.poll()
        if returncode is not None and not hasattr(self, '_logged'):
            logger.debug(f"Process exited: {returncode}")
            self._logged = True
        return returncode

    def wait(self, timeout=None):
        returncode = self._process.wait(timeout)
        logger.debug(f"Process wait returned: {returncode}")
        return returncode

    def __getattr__(self, name):
        """Transparent proxy for all other operations."""
        return getattr(self._process, name)
```

---

### Function: check_call_shim

**Purpose:** Wrapper for subprocess.check_call that adds logging.

**Location:** `src/splintercat/git/shim.py`

**Interface:**
```python
def check_call_shim(*args, **kwargs):
    """Log command and delegate to real subprocess.check_call."""
```

**Implementation:**
```python
def check_call_shim(*args, **kwargs):
    # Format command
    if isinstance(args[0], list):
        cmd_str = ' '.join(str(arg) for arg in args[0])
    else:
        cmd_str = str(args[0])

    cwd = kwargs.get('cwd')

    # Log and execute
    logger.debug("git-imerge check_call", command=cmd_str, cwd=cwd)

    try:
        result = real_subprocess.check_call(*args, **kwargs)
        logger.debug("check_call succeeded")
        return result
    except real_subprocess.CalledProcessError as e:
        logger.debug(f"check_call failed: {e.returncode}")
        raise
```

---

### Class: StreamCapture

**Purpose:** Wrapper for sys.stdout/stderr that logs all writes.

**Location:** `src/splintercat/git/shim.py`

**Interface:**
```python
class StreamCapture:
    """Wrapper for sys.stdout/stderr that logs writes to logfire.

    Optionally also writes to the original stream (default: yes).
    Buffers partial lines for cleaner logging.
    """

    def __init__(self, original_stream, stream_name: str,
                 echo_to_original: bool = True):
        """Initialize stream wrapper."""

    def write(self, text: str) -> int:
        """Write text, logging complete lines."""

    def flush(self):
        """Flush buffered content."""

    def __getattr__(self, name):
        """Forward other operations to original stream."""
```

**Key behaviors:**
- Buffers partial lines (git-imerge writes "Attempting..." then "success\n")
- Logs complete lines to logfire
- Optionally echoes to original stream (for terminal visibility)
- Maintains TextIOBase compatibility

**Implementation:**
```python
import sys
from io import TextIOBase

class StreamCapture(TextIOBase):
    def __init__(self, original_stream, stream_name: str, echo_to_original: bool = True):
        self.original_stream = original_stream
        self.stream_name = stream_name  # "stdout" or "stderr"
        self.echo_to_original = echo_to_original
        self._buffer = []  # Buffer for incomplete lines

    def write(self, text: str) -> int:
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
                if line:  # Skip empty
                    logger.info(
                        f"git-imerge {self.stream_name}",
                        message=line
                    )

            # Keep incomplete last line in buffer
            self._buffer = [lines[-1]] if lines[-1] else []

        # Echo to original stream if requested
        if self.echo_to_original:
            self.original_stream.write(text)
            self.original_stream.flush()

        return len(text)

    def flush(self):
        # Flush any incomplete line
        if self._buffer:
            incomplete = ''.join(self._buffer)
            if incomplete:
                logger.info(
                    f"git-imerge {self.stream_name}",
                    message=incomplete,
                    incomplete=True
                )
            self._buffer = []

        if self.echo_to_original:
            self.original_stream.flush()

    def __getattr__(self, name):
        return getattr(self.original_stream, name)
```

---

### Context Manager: capture_gitimerge_output

**Purpose:** Enable all three capture mechanisms, restore on exit.

**Location:** `src/splintercat/git/shim.py`

**Interface:**
```python
@contextmanager
def capture_gitimerge_output(echo_to_terminal: bool = True):
    """Context manager that captures all git-imerge output.

    Patches:
    1. gitimerge.subprocess.Popen -> PopenShim
    2. gitimerge.check_call -> check_call_shim
    3. sys.stdout -> StreamCapture
    4. sys.stderr -> StreamCapture

    Restores everything on exit.

    Args:
        echo_to_terminal: If True, also write to original stdout/stderr

    Usage:
        with capture_gitimerge_output():
            imerge = gitimerge.MergeState.initialize(...)
    """
```

**Implementation:**
```python
import sys
from contextlib import contextmanager

@contextmanager
def capture_gitimerge_output(echo_to_terminal: bool = True):
    import gitimerge

    # Save originals
    original_popen = gitimerge.subprocess.Popen
    original_check_call = gitimerge.check_call
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        # Patch subprocess in gitimerge's namespace
        gitimerge.subprocess.Popen = PopenShim
        gitimerge.check_call = check_call_shim

        # Patch stdout/stderr globally (affects all code)
        sys.stdout = StreamCapture(original_stdout, "stdout", echo_to_terminal)
        sys.stderr = StreamCapture(original_stderr, "stderr", echo_to_terminal)

        logger.info("git-imerge output capture enabled")

        yield

    finally:
        # Restore everything
        gitimerge.subprocess.Popen = original_popen
        gitimerge.check_call = original_check_call
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        logger.debug("git-imerge output capture disabled")
```

**Critical design decision:**
- subprocess patches are **module-specific** (only gitimerge.subprocess.Popen)
- stdout/stderr patches are **global** (sys.stdout/sys.stderr affect all code)
- This is acceptable because:
  - Context manager scope is narrow (just during IMerge operations)
  - Other code should use logger, not print()
  - Restore happens automatically on exit

---

### Integration: IMerge Class

**Purpose:** Use context manager to wrap all gitimerge operations.

**Location:** `src/splintercat/git/imerge.py`

**Pattern:**
```python
from splintercat.git.shim import capture_gitimerge_output

class IMerge:
    def start_merge(self, source_ref: str, target_branch: str):
        """Start merge with output capture."""
        with capture_gitimerge_output():
            # All gitimerge operations here
            self.git = gitimerge.GitRepository()
            # ... rest of implementation

    def get_current_conflict(self) -> tuple[int, int] | None:
        """Get conflict with output capture."""
        with capture_gitimerge_output():
            # ... implementation

    def continue_after_resolution(self):
        """Continue with output capture."""
        with capture_gitimerge_output():
            # ... implementation

    def finalize(self) -> str:
        """Finalize with output capture."""
        with capture_gitimerge_output():
            # ... implementation
```

**Why this pattern:**
- Each public method wraps its gitimerge calls
- Output capture is scoped to actual git operations
- No long-lived stream patching
- Explicit and clear

---

## Complete File Structure

### src/splintercat/git/shim.py
```
Lines   Purpose
-----   -------
1-30    Module docstring, imports
31-120  class PopenShim (subprocess.Popen wrapper)
121-150 def check_call_shim (subprocess.check_call wrapper)
151-230 class StreamCapture (stdout/stderr wrapper)
231-270 def capture_gitimerge_output (context manager)
271-280 Module-level constants/helpers if needed
```

Total: ~280 lines for all three capture mechanisms

### src/splintercat/git/imerge.py
```
Changes:
- Add import: from splintercat.git.shim import capture_gitimerge_output
- Wrap each public method body with: with capture_gitimerge_output():
```

Minimal changes: ~10 lines added total

### src/splintercat/core/runner.py
```
Changes:
- Add parameter: env: dict[str, str] | None = None
- Pass to invoke: if env: kwargs["env"] = env
```

Minimal changes: ~5 lines

---

## Testing Strategy

### Test File: tests/test_shim.py

**Test coverage:**

1. **PopenShim Tests**
   - test_popen_basic - Simple command execution
   - test_popen_with_pipes - stdin/stdout/stderr pipes
   - test_popen_logging - Verify logfire spans created
   - test_popen_forwards_attributes - pid, returncode, etc.

2. **check_call_shim Tests**
   - test_check_call_success - Successful execution
   - test_check_call_failure - CalledProcessError raised
   - test_check_call_logging - Verify logging

3. **StreamCapture Tests**
   - test_stream_capture_complete_lines - Buffering works
   - test_stream_capture_partial_lines - Buffer flushed correctly
   - test_stream_capture_echo - Original stream receives output
   - test_stream_capture_no_echo - Original stream not used

4. **Context Manager Tests**
   - test_context_manager_patches - Verify all patches applied
   - test_context_manager_restores - Verify restoration on exit
   - test_context_manager_exception - Restoration even on exception
   - test_module_isolation - Only gitimerge.subprocess patched

5. **Integration Tests**
   - test_imerge_operations - Real git-imerge operations logged
   - test_no_output_loss - All output captured
   - test_no_recursion - Runner still works

---

## Example Log Output

```
[INFO] git-imerge output capture enabled

[DEBUG] git-imerge subprocess command='git update-index -q --ignore-submodules --refresh' cwd='/repo'
[DEBUG] Started process PID 12345
[DEBUG] Process completed returncode=0 stdout_bytes=0 stderr_bytes=0

[INFO] git-imerge stderr message='Attempting to merge 1-1...'

[DEBUG] git-imerge subprocess command='git merge-tree ...' cwd='/repo'
[DEBUG] Started process PID 12346

[INFO] git-imerge stderr message='success.'

[DEBUG] Process completed returncode=0 stdout_bytes=256 stderr_bytes=0

[DEBUG] git-imerge check_call command='git update-ref -m ...' cwd='/repo'
[DEBUG] check_call succeeded

[INFO] git-imerge stderr message='Recording autofilled block Block(1, 1, 1, 1).'

[DEBUG] git-imerge output capture disabled
```

---

## Configuration

Optional: Add configuration for echo behavior:

```yaml
# config.yaml
config:
  git:
    imerge:
      log_output: true      # Enable output capture (default: true)
      echo_to_terminal: true  # Also show in terminal (default: true)
```

Usage in IMerge:
```python
def __init__(self, workdir: Path, name: str, goal: str = "merge"):
    # ... existing init
    self.echo_to_terminal = True  # From config

def start_merge(self, source_ref: str, target_branch: str):
    with capture_gitimerge_output(echo_to_terminal=self.echo_to_terminal):
        # ...
```

---

## Security Considerations

**Subprocess command logging:**
- Commands may contain sensitive data (tokens in URLs, etc.)
- Solution: Check for sensitive patterns before logging
- Alternative: Provide flag to disable command logging

**stdout/stderr capture:**
- Output may contain credentials or sensitive information
- Solution: git-imerge doesn't output secrets, but be aware
- Alternative: Add filtering for known secret patterns

---

## Performance Considerations

**Overhead:**
- PopenShim: ~100 microseconds per subprocess call (logging only)
- StreamCapture: ~10 microseconds per write() call
- Context manager: ~50 microseconds per enter/exit

**Impact:**
- Negligible compared to git command execution (milliseconds to seconds)
- Buffering in StreamCapture minimizes logging calls
- No I/O interception, just logging

---

## Future Enhancements

**Possible additions (not in initial implementation):**

1. **Separate log levels** - Different levels for subprocess vs stdout/stderr
2. **Filtering** - Skip logging for certain commands (like git status)
3. **Metrics** - Track subprocess count, execution time, output sizes
4. **Conditional capture** - Only capture on verbose mode
5. **Log file output** - Write raw output to file in addition to logfire

---

## Success Criteria

✅ All subprocess calls logged with command, cwd, returncode
✅ All sys.stderr progress messages logged
✅ All sys.stdout output logged
✅ Output still visible in terminal (configurable)
✅ No recursion or circular dependencies
✅ Only gitimerge subprocess namespace patched (not global)
✅ All streams restored after context manager exit
✅ Zero functional changes to git-imerge behavior
✅ All tests pass
✅ Complete observability of git-imerge operations
