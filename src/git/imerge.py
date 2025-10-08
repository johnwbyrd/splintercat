"""Wrapper around git-imerge library."""

import os
from pathlib import Path

import gitimerge


class IMerge:
    """Wrapper for git-imerge operations using the Python API."""

    def __init__(self, workdir: Path, name: str, goal: str = "merge"):
        """Initialize git-imerge wrapper.

        Args:
            workdir: Path to git repository
            name: Name for this imerge operation
            goal: Merge goal (merge, rebase, etc.)
        """
        self.workdir = workdir
        self.name = name
        self.goal = goal
        self.git = None
        self.merge_state = None

        # Change to workdir for git operations
        self._original_dir = os.getcwd()
        os.chdir(str(workdir))
        self.git = gitimerge.GitRepository()

    def start_merge(self, source_ref: str, target_branch: str):
        """Start an incremental merge.

        Args:
            source_ref: Source git ref to merge from
            target_branch: Target branch to merge into
        """
        # Require clean work tree
        self.git.require_clean_work_tree('proceed')

        # Get merge boundaries (returns merge_base, commits1, commits2)
        merge_base, commits1, commits2 = self.git.get_boundaries(
            target_branch, source_ref, first_parent=False
        )

        # Initialize merge state
        self.merge_state = gitimerge.MergeState.initialize(
            self.git,
            self.name,
            merge_base,
            target_branch,
            commits1,
            source_ref,
            commits2,
            goal=self.goal,
            branch=target_branch,
        )
        self.merge_state.save()

    def get_current_conflict(self) -> tuple[int, int] | None:
        """Get current conflict pair needing resolution.

        Returns:
            Tuple of (i1, i2) for next conflict, or None if no conflicts
        """
        if not self.merge_state:
            return None

        try:
            # Auto-complete what we can
            self.merge_state.auto_complete_frontier()
        except gitimerge.FrontierBlockedError as e:
            # Found a conflict - extract (i1, i2) from blocked frontier
            # The exception should indicate which merge is blocked
            return (e.i1, e.i2)
        except gitimerge.NothingToDoError:
            # Merge is complete
            return None

        return None

    def get_conflict_files(self, i1: int, i2: int) -> list[str]:
        """Get list of files with conflicts for a commit pair.

        Args:
            i1: Commit index from branch 1
            i2: Commit index from branch 2

        Returns:
            List of file paths with conflicts
        """
        # Request user merge for this conflict pair
        self.merge_state.request_user_merge(i1, i2)

        # Get conflicted files from git status
        output = gitimerge.check_output(
            ["git", "diff", "--name-only", "--diff-filter=U"], cwd=str(self.workdir)
        )
        return output.strip().split("\n") if output else []

    def continue_after_resolution(self):
        """Continue merge after user has resolved conflicts."""
        if not self.merge_state:
            return

        # Incorporate the user's manual merge
        self.merge_state.incorporate_user_merge()
        self.merge_state.save()

    def is_complete(self) -> bool:
        """Check if merge is complete.

        Returns:
            True if all conflicts resolved and ready to finalize
        """
        if not self.merge_state:
            return False

        try:
            self.merge_state.auto_complete_frontier()
            return True
        except (gitimerge.FrontierBlockedError, gitimerge.NothingToDoError):
            return False

    def finalize(self) -> str:
        """Simplify merge to single two-parent merge commit.

        Returns:
            SHA of final merge commit
        """
        if not self.merge_state:
            raise ValueError("No merge state to finalize")

        # Simplify to single merge commit
        refname = f"refs/heads/{self.merge_state.branch or 'HEAD'}"
        self.merge_state.simplify(refname)

        # Get the final commit SHA
        final_commit = self.git.get_commit_sha1(refname)
        return final_commit

    def __del__(self):
        """Cleanup: restore original directory."""
        if hasattr(self, "_original_dir"):
            os.chdir(self._original_dir)
