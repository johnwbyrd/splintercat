"""Wrapper around git-imerge library."""

from pathlib import Path


class IMergeWrapper:
    """Wrapper for git-imerge operations."""

    def __init__(self, workdir: Path, name: str):
        """Initialize git-imerge wrapper.

        Args:
            workdir: Path to git repository
            name: Name for this imerge operation
        """
        pass

    def start_merge(self, source_ref: str, target_branch: str):
        """Start an incremental merge.

        Args:
            source_ref: Source git ref to merge from
            target_branch: Target branch to merge into
        """
        pass

    def get_conflicts(self) -> list[tuple[int, int]]:
        """Get list of conflicting commit pairs.

        Returns:
            List of (i1, i2) tuples representing conflicting commit pairs
        """
        pass

    def get_conflict_files(self, i1: int, i2: int) -> list[str]:
        """Get list of files with conflicts for a commit pair.

        Args:
            i1: Commit index from branch 1
            i2: Commit index from branch 2

        Returns:
            List of file paths with conflicts
        """
        pass

    def finalize(self):
        """Simplify merge to single two-parent merge commit."""
        pass
