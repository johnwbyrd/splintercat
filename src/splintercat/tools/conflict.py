"""Layer 1 tools: Core conflict viewing and resolution."""

from pathlib import Path


class ViewConflictTool:
    """View a conflict with surrounding context."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Working directory containing files
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "view_conflict"

    @property
    def description(self) -> str:
        """Tool description."""
        return "View a merge conflict with surrounding context lines"

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "conflict_num": {
                    "type": "integer",
                    "description": "Conflict number (1-indexed)",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context (default 10)",
                },
            },
            "required": ["file", "conflict_num"],
        }

    def execute(
        self,
        file: str,
        conflict_num: int,
        context_lines: int = 10
    ) -> str:
        """Execute tool - view conflict with context.

        Args:
            file: File path
            conflict_num: Which conflict to view (1-indexed)
            context_lines: Lines of context before/after

        Returns:
            Formatted conflict view with context
        """
        # Implementation stub - Phase 2 will implement
        return f"Conflict {conflict_num} in {file} (implementation pending)"


class ViewMoreContextTool:
    """View conflict with custom context amounts."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Working directory
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "view_more_context"

    @property
    def description(self) -> str:
        """Tool description."""
        return "View conflict with custom before/after context lines"

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "conflict_num": {
                    "type": "integer",
                    "description": "Conflict number (1-indexed)"
                },
                "before": {
                    "type": "integer",
                    "description": "Lines before conflict"
                },
                "after": {
                    "type": "integer",
                    "description": "Lines after conflict"
                },
            },
            "required": ["file", "conflict_num", "before", "after"],
        }

    def execute(
        self,
        file: str,
        conflict_num: int,
        before: int,
        after: int
    ) -> str:
        """Execute tool.

        Args:
            file: File path
            conflict_num: Which conflict
            before: Lines before
            after: Lines after

        Returns:
            Formatted conflict view
        """
        # Implementation stub
        return (
            f"Conflict {conflict_num} in {file} with {before} "
            f"before, {after} after (pending)"
        )


class ResolveConflictTool:
    """Resolve a conflict with a choice."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Working directory
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "resolve_conflict"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Resolve conflict by choosing ours/theirs/both/custom"

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "File path"},
                "conflict_num": {
                    "type": "integer",
                    "description": "Conflict number (1-indexed)"
                },
                "choice": {
                    "type": "string",
                    "enum": ["ours", "theirs", "both", "custom"],
                    "description": "Resolution choice"
                },
                "custom_text": {
                    "type": "string",
                    "description": "Custom text (if choice is custom)",
                },
            },
            "required": ["file", "conflict_num", "choice"],
        }

    def execute(
        self,
        file: str,
        conflict_num: int,
        choice: str,
        custom_text: str | None = None
    ) -> str:
        """Execute tool - resolve conflict.

        Args:
            file: File path
            conflict_num: Which conflict
            choice: Resolution choice (ours/theirs/both/custom)
            custom_text: Custom resolution text

        Returns:
            Confirmation message
        """
        # Implementation stub
        return (
            f"Resolved conflict {conflict_num} in {file} with "
            f"choice: {choice} (pending)"
        )
