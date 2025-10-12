"""Layer 2 tools: Merge information."""

from pathlib import Path


class ShowMergeSummaryTool:
    """Show overview of merge operation."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Repository directory
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "show_merge_summary"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Show overview of current merge "
            "(source, target, conflicts)"
        )

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self) -> str:
        """Execute tool.

        Returns:
            Formatted merge summary
        """
        # Implementation stub
        return "Merge summary (implementation pending)"


class ListAllConflictsTool:
    """List all conflicts in merge."""

    def __init__(self, workdir: Path):
        """Initialize tool.

        Args:
            workdir: Repository directory
        """
        self.workdir = workdir

    @property
    def name(self) -> str:
        """Tool name."""
        return "list_all_conflicts"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "List all conflicts in the merge with files affected"
        )

    @property
    def parameters(self) -> dict:
        """Parameter schema."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self) -> str:
        """Execute tool.

        Returns:
            Formatted conflict list
        """
        # Implementation stub
        return "All conflicts (implementation pending)"
