"""Command execution tools for conflict resolution."""

import platform
import shlex

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.core.runner import Runner
from splintercat.tools.workspace import Workspace


def get_platform_key() -> str:
    """Determine platform key for command configuration.

    Returns:
        'windows' if running on Windows, 'posix' otherwise
    """
    return 'windows' if platform.system() == 'Windows' else 'posix'


def get_tool_commands_config(config) -> dict:
    """Get platform-specific tool commands configuration.

    Args:
        config: Configuration object with tools section

    Returns:
        Platform-specific command configuration dict
    """
    platform_key = get_platform_key()
    return config.tools.get(platform_key, {})


def validate_command(command: str, args: list[str], cmd_config: dict) -> None:
    """Validate command and arguments based on configuration.

    Generic validator that handles both simple commands and subcommands.

    Args:
        command: Command name
        args: All arguments (including subcommand if applicable)
        cmd_config: Command configuration from YAML

    Raises:
        ModelRetry: If validation fails
    """
    # Check if it has subcommands
    if cmd_config.get('has_subcommands'):
        if not args:
            raise ModelRetry(
                f"{command} requires a subcommand. "
                f"Use list_allowed_commands() for available subcommands."
            )

        subcommand = args[0]
        subcommand_args = args[1:]

        # Check subcommand blacklist
        blacklist = cmd_config.get('blacklist', {}).get('subcommands', [])
        if subcommand in blacklist:
            raise ModelRetry(
                f"{command} {subcommand} is blacklisted (dangerous operation)"
            )

        # Check subcommand whitelist
        subcommands = cmd_config.get('subcommands', {})
        if subcommand not in subcommands:
            available = ', '.join(subcommands.keys())
            raise ModelRetry(
                f"{command} {subcommand} not allowed. "
                f"Available subcommands: {available}"
            )

        # Validate subcommand args
        subcmd_config = subcommands[subcommand]
        _validate_args(
            f"{command} {subcommand}", subcommand_args, subcmd_config
        )
    else:
        # Simple command
        _validate_args(command, args, cmd_config)


def _validate_args(cmd_name: str, args: list[str], config: dict) -> None:
    """Validate flags and arguments.

    Args:
        cmd_name: Display name (e.g., 'grep' or 'git status')
        args: Arguments to validate
        config: Config with allowed_flags and allowed_args

    Raises:
        ModelRetry: If validation fails
    """
    allowed_flags = set(config.get('allowed_flags', []))
    allowed_args = config.get('allowed_args', [])

    for arg in args:
        if arg.startswith('-') or arg.startswith('/'):
            # It's a flag
            base_flag = arg.split('=')[0]
            if allowed_flags and base_flag not in allowed_flags:
                raise ModelRetry(
                    f"{cmd_name}: flag '{base_flag}' not allowed. "
                    f"Allowed flags: {', '.join(sorted(allowed_flags))}"
                )
        else:
            # Positional argument - check that some are allowed
            if not allowed_args:
                raise ModelRetry(
                    f"{cmd_name} does not accept positional arguments"
                )


def run_command(
    ctx: RunContext[Workspace],
    command: str,
    args: list[str]
) -> str:
    """Run a whitelisted command in the workspace directory.

    Args:
        command: Command to run (git, ls, cat, grep, findstr, etc.)
        args: List of arguments to pass to the command

    Returns:
        Command output including exit code, stdout, and stderr

    Raises:
        ModelRetry: If command or arguments not allowed

    Examples:
        run_command('git', ['status', '--porcelain'])
        run_command('git', ['show', ':2:path/to/file.cpp'])
        run_command('grep', ['-n', 'pattern', 'file.txt'])  # POSIX
        run_command('findstr', ['/N', 'pattern', 'file.txt'])  # Windows
    """
    workspace = ctx.deps

    # Get platform-specific configuration
    platform_config = get_tool_commands_config(workspace.config)

    # Check global blacklist
    blacklist = platform_config.get('blacklist', {})
    if command in blacklist.get('commands', []):
        raise ModelRetry(
            f"Command '{command}' is blacklisted (dangerous operation)"
        )

    # Validate command is whitelisted
    allowed = platform_config.get('allowed', {})
    if command not in allowed:
        available = ', '.join(allowed.keys())
        raise ModelRetry(
            f"Command '{command}' not allowed. "
            f"Available: {available}. "
            f"Use list_allowed_commands() for details."
        )

    cmd_config = allowed[command]

    # Generic validation (handles both simple and subcommand types)
    validate_command(command, args, cmd_config)

    # Build command string (runner takes string, not list)
    # Use shlex.quote to properly escape each argument
    cmd_parts = [command] + args
    cmd_string = ' '.join(shlex.quote(part) for part in cmd_parts)

    # Run command in workspace directory with timeout
    runner = Runner()
    try:
        result = runner.execute(
            cmd_string,
            cwd=workspace.workdir,
            timeout=30,
            check=False  # Don't raise on non-zero exit
        )

        output = f"Exit code: {result.exited}\n\n"
        if result.stdout:
            output += f"stdout:\n{result.stdout}\n"
        if result.stderr:
            output += f"stderr:\n{result.stderr}\n"

        return output

    except Exception as e:
        raise ModelRetry(
            f"Failed to run command '{command}': {e}"
        ) from e


def list_allowed_commands(ctx: RunContext[Workspace]) -> str:
    """List all whitelisted commands with usage examples.

    Returns:
        Formatted string showing available commands and examples
    """
    workspace = ctx.deps

    # Get prompt from config if available
    if hasattr(workspace, 'config') and workspace.config:
        prompts = workspace.config.prompts
        if 'commands' in prompts and 'allowed_list' in prompts['commands']:
            return prompts['commands']['allowed_list']

    # Generate from platform configuration
    platform_config = get_tool_commands_config(workspace.config)
    allowed = platform_config.get('allowed', {})

    output = f"Platform: {get_platform_key()}\n\n"
    output += "Available commands:\n\n"

    for cmd, config in allowed.items():
        desc = config.get('description', 'No description')
        output += f"  {cmd}: {desc}\n"

        if config.get('has_subcommands'):
            output += "    Subcommands:\n"
            subcommands = config.get('subcommands', {})
            for subcmd, subconfig in subcommands.items():
                subdesc = subconfig.get('description', '')
                output += f"      {subcmd}: {subdesc}\n"

    return output
