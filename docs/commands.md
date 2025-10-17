# Command Configuration System

## Overview

The command system controls which shell commands the LLM resolver can execute during conflict resolution. Commands are configured in YAML with platform-specific whitelists, validation rules, and descriptions.

## Design Principles

### 1. Honest Command Names

Commands are called by their actual names on each platform. No translation or aliasing.

**POSIX systems**: `grep`, `cat`, `find`
**Windows systems**: `findstr`, `type`, `dir`

The LLM learns which commands exist on which platform. If it doesn't know a command, that's fine - it will learn or ask.

### 2. Platform Detection

```python
platform_key = 'windows' if platform.system() == 'Windows' else 'posix'
```

Simple binary choice: Windows vs everything else (Linux, macOS, BSD, etc.).

### 3. Generic Subcommand System

Commands are either:
- **Simple**: `grep pattern file` (no subcommands)
- **Subcommand-based**: `git show ref` (has subcommands)

The `has_subcommands: true` flag enables subcommand validation for any command (git, docker, kubectl, cargo, etc.).

### 4. Configuration-Driven

All command definitions live in `defaults/tool-commands.yaml`. Users can override in their `splintercat.yaml`:

```yaml
config:
  tool_commands:
    posix:
      allowed:
        grep:
          allowed_flags: [-n, -i, -E, -r]  # Add -r flag
```

## Configuration Schema

### Simple Command

```yaml
config:
  tool_commands:
    posix:
      allowed:
        grep:
          description: "Search text using patterns"
          allowed_flags: [-n, -i, -E, -A, -B, -C, -v, -w, -c]
          allowed_args: ["{pattern}", "{file}"]
```

Fields:
- `description`: One-line documentation shown to LLM
- `allowed_flags`: Whitelisted flags (validated)
- `allowed_args`: Argument patterns (documentation, minimal validation)

### Command with Subcommands

```yaml
config:
  tool_commands:
    posix:
      allowed:
        git:
          has_subcommands: true
          description: "Git version control"
          subcommands:
            status:
              description: "Show working tree status"
              allowed_flags: [--porcelain, --short, -s, -b]
              allowed_args: []
            show:
              description: "Show commit or file contents"
              allowed_flags: [--stat, --oneline, --name-only]
              allowed_args: ["{ref}", ":1:{path}", ":2:{path}", ":3:{path}"]
          blacklist:
            subcommands: [push, pull, fetch, reset, rebase, merge, commit]
```

Fields:
- `has_subcommands`: Boolean flag enabling subcommand validation
- `subcommands`: Map of allowed subcommands with their own flags/args
- `blacklist.subcommands`: Forbidden subcommands (dangerous operations)

### Global Blacklist

```yaml
config:
  tool_commands:
    posix:
      blacklist:
        commands: [rm, mv, chmod, sudo, dd]

    windows:
      blacklist:
        commands: [del, format, reg, shutdown]
```

Dangerous commands that should never be allowed, regardless of configuration.

## Validation Logic

### 1. Global Blacklist Check

```python
if command in platform_config['blacklist']['commands']:
    raise ModelRetry("Command blacklisted")
```

### 2. Whitelist Check

```python
if command not in platform_config['allowed']:
    raise ModelRetry("Command not allowed")
```

### 3. Subcommand Validation (if `has_subcommands: true`)

```python
if cmd_config.get('has_subcommands'):
    subcommand = args[0]

    # Check subcommand blacklist
    if subcommand in cmd_config['blacklist']['subcommands']:
        raise ModelRetry("Subcommand blacklisted")

    # Check subcommand whitelist
    if subcommand not in cmd_config['subcommands']:
        raise ModelRetry("Subcommand not allowed")

    # Validate subcommand flags
    validate_flags(subcommand_args, subcmd_config['allowed_flags'])
```

### 4. Flag Validation

```python
for arg in args:
    if arg.startswith('-') or arg.startswith('/'):
        base_flag = arg.split('=')[0]
        if base_flag not in allowed_flags:
            raise ModelRetry("Flag not allowed")
```

Flags are strictly validated. Positional arguments are loosely validated (just check that some are allowed).

## Platform-Specific Commands

### POSIX Commands

```yaml
posix:
  allowed:
    git:
      has_subcommands: true
      description: "Git version control"
      # ... subcommands

    grep:
      description: "Search text using patterns"
      allowed_flags: [-n, -i, -E, -A, -B, -C]
      allowed_args: ["{pattern}", "{file}"]

    cat:
      description: "Display file contents"
      allowed_flags: [-n, -b, -s]
      allowed_args: ["{file}"]

    find:
      description: "Search for files"
      allowed_flags: [-name, -type, -maxdepth, -mindepth]
      allowed_args: ["{path}", "{pattern}"]

    ls:
      description: "List directory contents"
      allowed_flags: [-l, -a, -h, -t, -r, -1]
      allowed_args: ["{path}"]

    head:
      description: "Output first part of files"
      allowed_flags: [-n, -c]
      allowed_args: ["{file}"]

    tail:
      description: "Output last part of files"
      allowed_flags: [-n, -c, -f]
      allowed_args: ["{file}"]

    wc:
      description: "Count lines, words, characters"
      allowed_flags: [-l, -w, -c, -m]
      allowed_args: ["{file}"]

    file:
      description: "Determine file type"
      allowed_flags: [-b, -i]
      allowed_args: ["{file}"]

    pwd:
      description: "Print working directory"
      allowed_flags: []
      allowed_args: []
```

### Windows Commands

```yaml
windows:
  allowed:
    git:
      has_subcommands: true
      description: "Git version control (Git for Windows)"
      # Same subcommands as POSIX (git is cross-platform)

    findstr:
      description: "Search text in files"
      allowed_flags: [/N, /I, /V, /R, /C]
      allowed_args: ["{pattern}", "{file}"]

    type:
      description: "Display file contents"
      allowed_flags: []
      allowed_args: ["{file}"]

    dir:
      description: "List directory contents"
      allowed_flags: [/A, /B, /S, /O]
      allowed_args: ["{path}"]

    where:
      description: "Locate files"
      allowed_flags: [/R, /Q, /F]
      allowed_args: ["{path}", "{pattern}"]
```

Notes:
- Git works identically on Windows (Git for Windows provides Unix-like interface)
- Windows commands use `/` for flags instead of `-`
- Some POSIX utilities have no direct Windows equivalent (omitted from config)

## LLM Integration

### System Prompt

The LLM is told which commands are available via the `list_allowed_commands()` tool, which reads from configuration:

```python
def list_allowed_commands(ctx: RunContext[Workspace]) -> str:
    platform_config = get_tool_commands_config(workspace.config)

    output = f"Platform: {get_platform_key()}\n\n"
    output += "Available commands:\n\n"

    for cmd, config in platform_config['allowed'].items():
        output += f"  {cmd}: {config['description']}\n"

        if config.get('has_subcommands'):
            output += "    Subcommands:\n"
            for subcmd, subconfig in config['subcommands'].items():
                output += f"      {subcmd}: {subconfig['description']}\n"

    return output
```

Example output on POSIX:
```
Platform: posix

Available commands:

  git: Git version control
    Subcommands:
      status: Show working tree status
      show: Show commit or file contents
      diff: Show changes between commits

  grep: Search text using patterns
  cat: Display file contents
  find: Search for files
```

Example output on Windows:
```
Platform: windows

Available commands:

  git: Git version control (Git for Windows)
    Subcommands:
      status: Show working tree status
      show: Show commit or file contents

  findstr: Search text in files
  type: Display file contents
  dir: List directory contents
```

### Tool Call

LLM calls:
```python
run_command('grep', ['-n', 'pattern', 'file.txt'])  # POSIX
run_command('findstr', ['/N', 'pattern', 'file.txt'])  # Windows
```

No translation happens. Command names and flag syntax match the platform.

## Security Model

### Defense in Depth

1. **Global blacklist**: Dangerous commands (rm, del, format) forbidden entirely
2. **Per-command whitelist**: Only explicitly allowed commands can run
3. **Flag validation**: Only whitelisted flags accepted
4. **Subcommand blacklist**: Dangerous git operations (push, reset) forbidden
5. **Timeout**: All commands limited to 30 seconds
6. **Working directory**: Commands run in workspace directory only
7. **Shell escaping**: All arguments properly escaped via `shlex.quote()`

### Git Command Protection

Git subcommands are particularly dangerous because they can:
- Modify repository state (commit, reset, rebase)
- Communicate with remote servers (push, pull, fetch)
- Change configuration (config)

Blacklist includes:
- `push`, `pull`, `fetch`: Network operations
- `reset`, `rebase`, `merge`, `commit`: State modifications
- `config`: Configuration changes
- `clean`, `branch`, `tag`: Destructive operations

Only read-only operations and file staging (add, rm for conflict resolution) are allowed.

## Adding New Commands

### Simple Command

To add a new simple command (e.g., `rg` - ripgrep):

```yaml
config:
  tool_commands:
    posix:
      allowed:
        rg:
          description: "Search code using ripgrep (faster grep)"
          allowed_flags: [-n, -i, -t, -g, -A, -B, -C]
          allowed_args: ["{pattern}", "{path}"]
```

### Command with Subcommands

To add a new subcommand-based tool (e.g., `cargo`):

```yaml
config:
  tool_commands:
    posix:
      allowed:
        cargo:
          has_subcommands: true
          description: "Rust package manager"
          subcommands:
            check:
              description: "Check code without building"
              allowed_flags: [--all, --tests]
              allowed_args: []
            test:
              description: "Run tests"
              allowed_flags: [--no-fail-fast, --release]
              allowed_args: ["{test_name}"]
          blacklist:
            subcommands: [publish, install, clean]
```

## User Customization

Users can override command definitions in their `splintercat.yaml`:

```yaml
config:
  tool_commands:
    posix:
      allowed:
        # Add custom flags to grep
        grep:
          allowed_flags: [-n, -i, -E, -A, -B, -C, -r, -R]

        # Add ripgrep as alternative
        rg:
          description: "Fast text search"
          allowed_flags: [-n, -i, -t, -g]
          allowed_args: ["{pattern}", "{path}"]
```

Deep merge ensures user customization overrides defaults while preserving unchanged settings.

## Implementation Details

### Code Location

- Configuration: `src/splintercat/defaults/tool-commands.yaml`
- Implementation: `src/splintercat/tools/commands.py`
- Tests: `tests/test_commands.py`

### Key Functions

```python
def get_platform_key() -> str:
    """Returns 'windows' or 'posix'"""

def get_tool_commands_config(config) -> dict:
    """Load platform-specific command config"""

def validate_command(command: str, args: list[str], cmd_config: dict) -> None:
    """Validate command and arguments (simple or subcommand)"""

def run_command(ctx: RunContext[Workspace], command: str, args: list[str]) -> str:
    """Execute validated command and return output"""

def list_allowed_commands(ctx: RunContext[Workspace]) -> str:
    """Generate help text for LLM"""
```

### Error Messages

Validation errors use `ModelRetry` exception to provide feedback to LLM:

```python
raise ModelRetry(
    f"Command '{command}' not allowed. "
    f"Available: {', '.join(allowed_commands)}. "
    f"Use list_allowed_commands() for details."
)

raise ModelRetry(
    f"git {subcommand} is blacklisted (dangerous operation)"
)

raise ModelRetry(
    f"grep flag '-x' not allowed. "
    f"Allowed flags: -n, -i, -E, -A, -B, -C"
)
```

These messages help the LLM understand what went wrong and retry with correct syntax.

## Testing Strategy

### Platform-Specific Tests

Tests check platform detection and use appropriate commands:

```python
def test_grep_on_posix():
    if get_platform_key() == 'windows':
        pytest.skip("POSIX-only test")

    result = run_command(ctx, 'grep', ['-n', 'pattern', 'file'])
    assert "Exit code: 0" in result

def test_findstr_on_windows():
    if get_platform_key() == 'posix':
        pytest.skip("Windows-only test")

    result = run_command(ctx, 'findstr', ['/N', 'pattern', 'file'])
    assert "Exit code: 0" in result
```

### Validation Tests

```python
def test_blacklisted_command():
    with pytest.raises(ModelRetry, match="blacklisted"):
        run_command(ctx, 'rm', ['-rf', '/'])

def test_blacklisted_git_subcommand():
    with pytest.raises(ModelRetry, match="blacklisted"):
        run_command(ctx, 'git', ['push', 'origin', 'main'])

def test_invalid_flag():
    with pytest.raises(ModelRetry, match="not allowed"):
        run_command(ctx, 'grep', ['-Z', 'pattern', 'file'])

def test_subcommand_flag_validation():
    with pytest.raises(ModelRetry, match="not allowed"):
        run_command(ctx, 'git', ['status', '--invalid-flag'])
```

### Cross-Platform Tests

Some tests work on all platforms (like git):

```python
def test_git_status():
    # Works on both POSIX and Windows
    result = run_command(ctx, 'git', ['status', '--porcelain'])
    assert "Exit code: 0" in result
```

## Future Extensions

### Possible Enhancements

1. **Argument pattern validation**: Validate positional args against patterns like `{ref}`, `{path}`
2. **Flag value validation**: Check that `--max-count=N` has numeric N
3. **Command aliases**: Allow `ll` → `ls -la` mapping in config
4. **Conditional availability**: Mark commands as requiring certain packages/versions
5. **Usage examples**: Include example commands in configuration for LLM reference

### Not Planned

1. **Flag translation**: No automatic `-n` → `/N` mapping (LLM uses platform-appropriate syntax)
2. **Command translation**: No `grep` → `findstr` aliasing (use honest names)
3. **Cross-platform abstraction**: No unified API (different platforms are different)

The system stays simple: configuration defines what's available, validation enforces rules, LLM adapts to platform.
