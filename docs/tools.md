# Tool System

## Overview

The tool system provides the LLM resolver with shell commands for investigating and resolving merge conflicts. Tools are configured in tools.yaml with platform-specific definitions, validation rules, and descriptions.

## Design Philosophy

### Honest Command Names

Commands use their actual platform names - no translation or aliasing. POSIX systems use grep, cat, find, ls. Windows systems use findstr, type, dir, where. The LLM learns which commands exist on each platform and uses list_allowed_commands() to discover available tools.

### Platform Detection

Simple binary choice: Windows vs everything else (Linux, macOS, BSD). All non-Windows systems use POSIX commands.

### Configuration-Driven

All tool definitions live in tools.yaml. Users customize via splintercat.yaml. Changes take effect without code modifications.

## Tool Types

### Simple Tools

Commands without subcommands like grep, cat, find. Each tool specifies its description, allowed flags, and argument patterns.

### Subcommand Tools

Commands with subcommands like git, docker, kubectl, cargo. The has_subcommands flag enables generic subcommand validation. Each subcommand has its own description, allowed flags, and argument patterns. Blacklists prevent dangerous subcommands from executing.

## Security

### Defense in Depth

- **Global blacklist**: Dangerous commands forbidden entirely
- **Per-tool whitelist**: Only explicitly allowed tools can run
- **Flag validation**: Only whitelisted flags accepted
- **Subcommand blacklist**: Dangerous operations forbidden
- **Timeout**: 30 second limit per command
- **Working directory**: Commands run in workspace only
- **Shell escaping**: Arguments automatically escaped

### Git Protection

Git subcommands are particularly dangerous.

**Blacklisted** (dangerous):
- push, pull, fetch - Network operations
- reset, rebase, merge, commit - State modifications
- config - Configuration changes
- clean, branch, tag - Destructive operations

**Allowed** (read-only + staging):
- status, show, diff, log - Inspection
- ls-files, cat-file, rev-parse - Object queries
- add, rm - Staging for conflict resolution only
- checkout - File restoration with --ours/--theirs

## Platform-Specific Tools

### POSIX Tools

Git works cross-platform via Git for Windows. Text search uses grep with extended regex. File search uses find with name patterns. File display uses cat with line numbering. Directory listing uses ls with long format and human-readable sizes. File head and tail commands available with line/byte counts. Word count via wc. File type detection via file command. Print working directory via pwd.

Global blacklist prevents rm, mv, cp, chmod, sudo, dd.

### Windows Tools

Git works the same as POSIX via Git for Windows. Text search uses findstr with different regex syntax than grep. File display uses type command. Directory listing uses dir command. File search uses where command.

Global blacklist prevents del, format, rmdir, reg, shutdown.

## LLM Integration

### Tool Discovery

LLM calls list_allowed_commands() to see available tools. The response shows the current platform, lists all commands with descriptions, and for subcommand tools shows available subcommands with their descriptions.

### Tool Invocation

LLM calls tools with platform-appropriate syntax. On POSIX, it uses grep with dash flags. On Windows, it uses findstr with slash flags. No translation happens - commands match the platform.

### Error Messages

Validation errors provide helpful feedback indicating whether commands are blacklisted, not in the whitelist, or using disallowed flags. Messages show available alternatives.

## Adding New Tools

### Simple Tool

Add tool definition to tools.yaml under platform-specific allowed section. Specify description, allowed flags, and argument patterns.

### Subcommand Tool

Add tool with has_subcommands flag set to true. Define each subcommand with its description, allowed flags, and argument patterns. Add dangerous subcommands to blacklist section.

## Implementation

### Code Location

Configuration in src/splintercat/defaults/tools.yaml. Implementation in src/splintercat/tools/commands.py. Tests in tests/test_commands.py.

### Key Functions

get_platform_key() returns windows or posix. get_tool_commands_config() loads platform-specific tool config. validate_command() validates command and arguments. run_command() executes validated command and returns output. list_allowed_commands() generates help text for LLM.

### Validation Flow

Check global blacklist. Check tool whitelist. For subcommand tools, check subcommand blacklist, check subcommand whitelist, validate subcommand flags. For simple tools, validate flags. Execute with 30s timeout. Return formatted output.

## Testing

### Platform-Specific Tests

Tests detect platform and skip appropriately. POSIX tests skip on Windows. Windows tests skip on POSIX.

### Cross-Platform Tests

Git tests work everywhere since Git for Windows provides consistent interface.

### Validation Tests

Test security enforcement for blacklisted commands, blacklisted subcommands, and invalid flags.

## User Customization

Users override tool definitions in splintercat.yaml. Can add new tools like ripgrep. Can extend existing tools with additional flags. Deep merge preserves defaults while applying customizations.

## Future Extensions

Possible enhancements not currently implemented:

**Argument pattern validation**: Validate args against patterns like ref or path

**Flag value validation**: Check numeric values in flag arguments

**Command aliases**: Map shortened commands to full commands with flags

**Conditional availability**: Mark tools as requiring specific packages

**Usage examples**: Include example commands for LLM reference

The system stays simple: configuration defines available tools, validation enforces rules, LLM adapts to platform.

**Fix model format in config and examples to use "provider:model" syntax with colon**: This enhances flexibility for users running local models and documents cross-platform behavior.