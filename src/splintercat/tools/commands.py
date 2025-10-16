"""Command execution tools for conflict resolution."""

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.core.runner import Runner
from splintercat.tools.workspace import Workspace

# Whitelisted commands and their allowed subcommands
ALLOWED_COMMANDS = {
    'git': {
        'subcommands': [
            'status', 'show', 'diff', 'ls-files', 'log',
            'add', 'rm', 'checkout', 'cat-file', 'rev-parse',
            'merge-base', 'diff-tree'
        ],
    },
    'ls': {},
    'cat': {},
    'head': {},
    'tail': {},
    'wc': {},
    'file': {},
    'grep': {},
    'find': {},
    'pwd': {},
}

# Dangerous shell metacharacters
SHELL_METACHARACTERS = [
    '&', '|', ';', '`', '$', '\n', '&&', '||', '>', '<', '>>'
]


def run_command(
    ctx: RunContext[Workspace],
    command: str,
    args: list[str]
) -> str:
    """Run a whitelisted command in the workspace directory.

    Args:
        command: Command to run (git, ls, cat, head, tail, etc.)
        args: List of arguments to pass to the command

    Returns:
        Command output including exit code, stdout, and stderr

    Raises:
        ModelRetry: If command is not whitelisted or contains
            unsafe characters

    Examples:
        run_command('git', ['status', '--porcelain'])
        run_command('git', ['show', ':2:path/to/file.cpp'])
        run_command('cat', ['file.txt'])
        run_command('head', ['-n', '50', 'file.txt'])
        run_command('grep', ['-n', 'pattern', 'file.txt'])
    """
    workspace = ctx.deps

    # Validate command is whitelisted
    if command not in ALLOWED_COMMANDS:
        available = ', '.join(ALLOWED_COMMANDS.keys())
        raise ModelRetry(
            f"Command '{command}' not allowed. "
            f"Available commands: {available}. "
            f"Use list_allowed_commands() for full details."
        )

    # Validate arguments don't contain shell metacharacters
    for arg in args:
        for metachar in SHELL_METACHARACTERS:
            if metachar in arg:
                raise ModelRetry(
                    f"Argument contains unsafe character '{metachar}': {arg}\n"
                    f"Shell metacharacters are not allowed for security."
                )

    # For git, validate subcommand
    if command == 'git':
        if not args:
            raise ModelRetry(
                "git command requires a subcommand. "
                f"Allowed: {', '.join(ALLOWED_COMMANDS['git']['subcommands'])}"
            )

        subcommand = args[0]
        if subcommand not in ALLOWED_COMMANDS['git']['subcommands']:
            allowed = ', '.join(ALLOWED_COMMANDS['git']['subcommands'])
            raise ModelRetry(
                f"git {subcommand} not allowed. "
                f"Allowed git subcommands: {allowed}"
            )

    # Build command string (runner takes string, not list)
    # Args are already validated against shell metacharacters
    cmd_parts = [command] + args
    cmd_string = ' '.join(cmd_parts)

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

    # Fallback if config not available
    return "Use run_command() with: " + ", ".join(ALLOWED_COMMANDS.keys())
