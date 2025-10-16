"""Workspace and file manipulation tools for conflict resolution."""

import json
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry


class Workspace:
    """Workspace for conflict resolution.

    Provides access to git working directory where conflicts exist.
    """

    def __init__(
        self,
        workdir: Path,
        conflict_files: list[str],
        config=None
    ):
        """Initialize workspace.

        Args:
            workdir: Git working directory containing conflicts
            conflict_files: List of file paths with conflicts
            config: Optional configuration object
        """
        self.workdir = workdir
        self.conflict_files = conflict_files
        self.config = config


# Pydantic AI compatible standalone tool functions


def read_file(
    ctx: RunContext[Workspace],
    filepath: str,
    start_line: int = 1,
    num_lines: int = 50
) -> str:
    """Read file with line numbers.

    Args:
        filepath: Path to file (relative to workspace)
        start_line: First line to read (1-indexed)
        num_lines: Number of lines to read (default 50, use -1
            for entire file)

    Returns:
        File content with line numbers: "1: content\\n2: content\\n..."

    Raises:
        ModelRetry: If file not found or cannot be read
    """
    workspace = ctx.deps
    file_path = workspace.workdir / filepath

    if not file_path.exists():
        raise ModelRetry(
            f"File '{filepath}' not found in workspace. "
            f"Use run_command('ls', ['-la']) to see available files."
        )

    try:
        content = file_path.read_text()
    except Exception as e:
        raise ModelRetry(f"Failed to read '{filepath}': {e}") from e

    lines = content.splitlines()

    # Determine which lines to show
    if num_lines == -1:
        # Show entire file
        selected_lines = lines[start_line - 1:]
    else:
        # Show specified range
        end_line = start_line + num_lines - 1
        selected_lines = lines[start_line - 1:end_line]

    # Format with line numbers
    output = []
    for i, line in enumerate(selected_lines, start=start_line):
        output.append(f"{i}: {line}")

    return "\n".join(output)


def write_file(
    ctx: RunContext[Workspace],
    filepath: str,
    content: str
) -> str:
    """Create or completely replace a file.

    Args:
        filepath: Path to file (relative to workspace)
        content: File content to write

    Returns:
        Confirmation message with file size

    Raises:
        ModelRetry: If file cannot be written
    """
    workspace = ctx.deps
    file_path = workspace.workdir / filepath

    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_path.write_text(content)
    except Exception as e:
        raise ModelRetry(f"Failed to write '{filepath}': {e}") from e

    byte_count = len(content.encode('utf-8'))
    line_count = len(content.splitlines())
    return f"Wrote {byte_count} bytes ({line_count} lines) to {filepath}"


def concatenate_to_file(
    ctx: RunContext[Workspace],
    output_filepath: str,
    sources: list[str]
) -> str:
    """Build output file by concatenating source files in order.

    Args:
        output_filepath: Path to output file
        sources: List of source file paths to concatenate

    Returns:
        Confirmation message

    Raises:
        ModelRetry: If any source file not found or cannot be read
    """
    workspace = ctx.deps

    # Read all source files
    parts = []
    for source in sources:
        source_path = workspace.workdir / source
        if not source_path.exists():
            raise ModelRetry(
                f"Source file '{source}' not found. "
                f"Cannot concatenate."
            )
        try:
            parts.append(source_path.read_text())
        except Exception as e:
            raise ModelRetry(
                f"Failed to read source '{source}': {e}"
            ) from e

    # Concatenate with newlines between files
    concatenated = "\n".join(parts)

    # Write output
    output_path = workspace.workdir / output_filepath
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        output_path.write_text(concatenated)
    except Exception as e:
        raise ModelRetry(
            f"Failed to write '{output_filepath}': {e}"
        ) from e

    line_count = len(concatenated.splitlines())
    return (
        f"Created {output_filepath} ({line_count} lines) "
        f"from {len(sources)} source files"
    )


def submit_resolution(
    ctx: RunContext[Workspace],
    filepath: str,
    confirm_size_change: bool = False,
    confirm_empty: bool = False,
    skip_syntax_check: bool = False
) -> str:
    """Submit resolved file with validation.

    Performs safety checks:
    - No conflict markers remain
    - Syntax validation for Python/JSON/YAML
    - Size change warnings
    - Empty file warnings

    Args:
        filepath: Path to resolved file
        confirm_size_change: Bypass size change warnings
        confirm_empty: Confirm empty file is intentional
        skip_syntax_check: Skip syntax validation

    Returns:
        Resolution content or deletion confirmation

    Raises:
        ModelRetry: If validation fails with fix instructions
    """
    workspace = ctx.deps
    file_path = workspace.workdir / filepath

    # Check if file was deleted (git rm)
    if not file_path.exists():
        # TODO: Check git status to confirm deletion
        # For now, just confirm the file doesn't exist
        return f"File {filepath} does not exist (deleted)."

    # Read resolution content
    try:
        content = file_path.read_text()
    except Exception as e:
        raise ModelRetry(f"Failed to read '{filepath}': {e}") from e

    # Check for conflict markers
    conflict_markers = ['<<<<<<<', '=======', '>>>>>>>']
    for marker in conflict_markers:
        if marker in content:
            raise ModelRetry(
                f"Resolution still contains conflict marker '{marker}'. "
                f"Please remove all conflict markers before submitting."
            )

    # Check for empty file
    if not content.strip() and not confirm_empty:
        raise ModelRetry(
            f"Resolution file '{filepath}' is empty. "
            f"If intentional, call submit_resolution with "
            f"confirm_empty=True. "
            f"To delete the file, use: run_command('git', "
            f"['rm', '{filepath}'])"
        )

    # Syntax checking for known file types
    if not skip_syntax_check:
        if filepath.endswith('.py'):
            try:
                compile(content, filepath, 'exec')
            except SyntaxError as e:
                raise ModelRetry(
                    f"Python syntax error at line {e.lineno}: {e.msg}\n"
                    f"Please fix the syntax error before submitting."
                ) from e

        elif filepath.endswith('.json'):
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                raise ModelRetry(
                    f"JSON syntax error at line {e.lineno}: {e.msg}\n"
                    f"Please fix the JSON syntax before submitting."
                ) from e

        elif filepath.endswith(('.yaml', '.yml')):
            try:
                import yaml
                yaml.safe_load(content)
            except Exception as e:
                raise ModelRetry(
                    f"YAML syntax error: {e}\n"
                    f"Please fix the YAML syntax before submitting."
                ) from e

    # TODO: Size change detection (need to compare with original)
    # For now, just return success

    byte_count = len(content.encode('utf-8'))
    line_count = len(content.splitlines())
    return (
        f"Resolution validated for {filepath}: "
        f"{byte_count} bytes, {line_count} lines. "
        f"Content returned."
    )
