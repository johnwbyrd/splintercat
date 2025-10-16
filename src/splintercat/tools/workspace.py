"""File-based workspace for conflict resolution."""

from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.tools.parser import Conflict


@dataclass
class File:
    """Metadata for a workspace file."""

    content: str
    description: str
    required: bool = False

    @property
    def line_count(self) -> int:
        """Count lines in file content."""
        return len(self.content.splitlines()) if self.content else 0


class Workspace:
    """Workspace containing files for one conflict."""

    def __init__(self, conflict: Conflict, workspace_id: str):
        """Initialize workspace from parsed conflict.

        Args:
            conflict: Parsed conflict data
            workspace_id: Unique identifier for workspace directory
        """
        self.workdir = Path("/tmp") / f"conflict_{workspace_id}"
        self.workdir.mkdir(parents=True, exist_ok=True)

        # Create file metadata for all workspace files
        self.files = {
            "ours": File(
                content=conflict.ours_content,
                description=f"Content from our branch ({conflict.ours_ref})",
                required=False,
            ),
            "theirs": File(
                content=conflict.theirs_content,
                description=(
                    f"Content from their branch ({conflict.theirs_ref})"
                ),
                required=False,
            ),
            "before": File(
                content="\n".join(conflict.context_before),
                description=(
                    "Context before conflict - MUST be first in resolution"
                ),
                required=True,
            ),
            "after": File(
                content="\n".join(conflict.context_after),
                description=(
                    "Context after conflict - MUST be last in resolution"
                ),
                required=True,
            ),
        }

        # Add base if present (diff3 format)
        if conflict.base_content is not None:
            self.files["base"] = File(
                content=conflict.base_content,
                description="Content from merge base (common ancestor)",
                required=False,
            )

        # Write all files to disk
        for filename, file in self.files.items():
            self._write_to_disk(filename, file.content)

    def _write_to_disk(self, filename: str, content: str):
        """Write file to workspace directory.

        Args:
            filename: Name of file to write
            content: Content to write
        """
        (self.workdir / filename).write_text(content)


class Tools:
    """Tools for working with conflict workspace."""

    def __init__(self, workspace: Workspace):
        """Initialize tools with workspace.

        Args:
            workspace: Workspace to operate on
        """
        self.workspace = workspace

    def list_files(self) -> str:
        """List all files with descriptions and line counts.

        Returns:
            Formatted string showing available files
        """
        lines = ["Available files in workspace:\n"]

        for filename, file in self.workspace.files.items():
            lines.append(f"  {filename} ({file.line_count} lines)")
            lines.append(f"    {file.description}\n")

        return "\n".join(lines)

    def read_file(
        self,
        name: str,
        start_line: int = 1,
        end_line: int | None = None
    ) -> str:
        """Read file content with line numbers.

        Args:
            name: Filename to read
            start_line: First line to read (1-indexed)
            end_line: Last line to read (None = show first 20 lines)

        Returns:
            File content with line numbers, or error message
        """
        if name not in self.workspace.files:
            return (
                f"Error: File '{name}' not found. "
                f"Use list_files() to see available files."
            )

        content = self.workspace.files[name].content
        lines = content.splitlines()

        # Default to first 20 lines if no end specified
        if end_line is None:
            end_line = min(len(lines), 20)

        # Extract range (1-indexed)
        selected_lines = lines[start_line - 1:end_line]

        # Format with line numbers
        output = []
        for i, line in enumerate(selected_lines, start=start_line):
            output.append(f"  {i}: {line}")

        return "\n".join(output)

    def write_file(
        self,
        name: str,
        content: str,
        description: str = ""
    ) -> str:
        """Create new file in workspace.

        Args:
            name: Filename to create
            content: File content
            description: Optional description of file purpose

        Returns:
            Confirmation message with line count
        """
        self.workspace.files[name] = File(
            content=content,
            description=description or "User-created file",
            required=False,
        )
        self.workspace._write_to_disk(name, content)

        line_count = len(content.splitlines())
        return f"Created {name} ({line_count} lines)"

    def cat_files(
        self,
        input_files: list[str],
        output_file: str
    ) -> str:
        """Concatenate multiple files into output file.

        Args:
            input_files: List of filenames to concatenate (in order)
            output_file: Name of output file to create

        Returns:
            Confirmation message or error
        """
        # Validate all input files exist
        for filename in input_files:
            if filename not in self.workspace.files:
                return f"Error: File '{filename}' not found"

        # Concatenate with newlines between files
        parts = [
            self.workspace.files[f].content
            for f in input_files
        ]
        concatenated = "\n".join(parts)

        # Create output file
        self.workspace.files[output_file] = File(
            content=concatenated,
            description=f"Concatenation of {len(input_files)} files",
            required=False,
        )
        self.workspace._write_to_disk(output_file, concatenated)

        line_count = len(concatenated.splitlines())
        return (
            f"Created {output_file} ({line_count} lines) "
            f"from {len(input_files)} files"
        )

    def submit_resolution(self, filename: str) -> str:
        """Submit resolution file for validation.

        Args:
            filename: Name of file containing resolution

        Returns:
            Resolution content if valid, or error message

        Raises:
            ModelRetry: If resolution is invalid, with instructions for fixing
        """
        if filename not in self.workspace.files:
            raise ModelRetry(
                f"File '{filename}' not found. Use list_files() to see available files."
            )

        resolution = self.workspace.files[filename].content
        before = self.workspace.files["before"].content
        after = self.workspace.files["after"].content

        # Validate structure - must include required context
        if not resolution.startswith(before):
            raise ModelRetry(
                "Resolution must start with 'before' content. "
                f"Current resolution starts with: {resolution[:100]!r}... "
                f"but should start with: {before[:100]!r}..."
            )

        if not resolution.endswith(after):
            raise ModelRetry(
                "Resolution must end with 'after' content. "
                f"Current resolution ends with: ...{resolution[-100:]!r} "
                f"but should end with: ...{after[-100:]!r}"
            )

        # Return the resolved content
        return resolution


# Pydantic AI compatible standalone tool functions


def list_files(ctx: RunContext[Workspace]) -> str:
    """List all files with descriptions and line counts.

    Returns:
        Formatted string showing available files
    """
    workspace = ctx.deps
    lines = ["Available files in workspace:\n"]

    for filename, file in workspace.files.items():
        lines.append(f"  {filename} ({file.line_count} lines)")
        lines.append(f"    {file.description}\n")

    return "\n".join(lines)


def read_file(
    ctx: RunContext[Workspace],
    name: str,
    start_line: int = 1,
    end_line: int | None = None
) -> str:
    """Read file content with line numbers.

    Args:
        name: Filename to read
        start_line: First line to read (1-indexed)
        end_line: Last line to read (None = show first 20 lines)

    Returns:
        File content with line numbers, or error message
    """
    workspace = ctx.deps

    if name not in workspace.files:
        return (
            f"Error: File '{name}' not found. "
            f"Use list_files() to see available files."
        )

    content = workspace.files[name].content
    lines = content.splitlines()

    # Default to first 20 lines if no end specified
    if end_line is None:
        end_line = min(len(lines), 20)

    # Extract range (1-indexed)
    selected_lines = lines[start_line - 1:end_line]

    # Format with line numbers
    output = []
    for i, line in enumerate(selected_lines, start=start_line):
        output.append(f"  {i}: {line}")

    return "\n".join(output)


def write_file(
    ctx: RunContext[Workspace],
    name: str,
    content: str,
    description: str = ""
) -> str:
    """Create new file in workspace.

    Args:
        name: Filename to create
        content: File content
        description: Optional description of file purpose

    Returns:
        Confirmation message with line count
    """
    workspace = ctx.deps

    workspace.files[name] = File(
        content=content,
        description=description or "User-created file",
        required=False,
    )
    workspace._write_to_disk(name, content)

    line_count = len(content.splitlines())
    return f"Created {name} ({line_count} lines)"


def cat_files(
    ctx: RunContext[Workspace],
    input_files: list[str],
    output_file: str
) -> str:
    """Concatenate multiple files into output file.

    Args:
        input_files: List of filenames to concatenate (in order)
        output_file: Name of output file to create

    Returns:
        Confirmation message or error
    """
    workspace = ctx.deps

    # Validate all input files exist
    for filename in input_files:
        if filename not in workspace.files:
            return f"Error: File '{filename}' not found"

    # Concatenate with newlines between files
    parts = [
        workspace.files[f].content
        for f in input_files
    ]
    concatenated = "\n".join(parts)

    # Create output file
    workspace.files[output_file] = File(
        content=concatenated,
        description=f"Concatenation of {len(input_files)} files",
        required=False,
    )
    workspace._write_to_disk(output_file, concatenated)

    line_count = len(concatenated.splitlines())
    return (
        f"Created {output_file} ({line_count} lines) "
        f"from {len(input_files)} files"
    )


def submit_resolution(
    ctx: RunContext[Workspace],
    filename: str
) -> str:
    """Submit resolution file for validation.

    Args:
        filename: Name of file containing resolution

    Returns:
        Resolution content if valid

    Raises:
        ModelRetry: If resolution is invalid, with instructions for fixing
    """
    workspace = ctx.deps

    if filename not in workspace.files:
        raise ModelRetry(
            f"File '{filename}' not found. Use list_files() to see available files."
        )

    resolution = workspace.files[filename].content
    before = workspace.files["before"].content
    after = workspace.files["after"].content

    # Validate structure - must include required context
    if not resolution.startswith(before):
        raise ModelRetry(
            "Resolution must start with 'before' content. "
            f"Current resolution starts with: {resolution[:100]!r}... "
            f"but should start with: {before[:100]!r}..."
        )

    if not resolution.endswith(after):
        raise ModelRetry(
            "Resolution must end with 'after' content. "
            f"Current resolution ends with: ...{resolution[-100:]!r} "
            f"but should end with: ...{after[-100:]!r}"
        )

    # Return the resolved content
    return resolution
