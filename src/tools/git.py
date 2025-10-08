"""Layer 2 tools: Git investigation."""

from pathlib import Path


class GitShowCommitTool:
    """Show commit information and changes."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Git repository directory
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "git_show_commit"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Show commit message and changes for a ref"

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "Git ref (SHA, HEAD, FETCH_HEAD, etc)",
                },
                "file": {
                    "type": "string",
                    "description": "Optional: show changes only for this file",
                },
            },
            "required": ["ref"],
        }

    def execute(self, ref: str, file: str | None = None) -> str:
        """Execute tool.

        Args:
            ref: Git reference
            file: Optional file filter

        Returns:
            Formatted commit information
        """
        # Implementation stub
        return f"Commit {ref} (implementation pending)"


class GitLogTool:
    """Show git log history."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Git repository directory
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "git_log"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Show recent commit history, optionally for a file"

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Optional: log for specific file"},
                "max_count": {"type": "integer", "description": "Number of commits (default 10)"},
            },
            "required": [],
        }

    def execute(self, file: str | None = None, max_count: int = 10) -> str:
        """Execute tool.

        Args:
            file: Optional file to filter log
            max_count: Number of commits to show

        Returns:
            Formatted git log
        """
        # Implementation stub
        return f"Git log (max {max_count} commits) (implementation pending)"
