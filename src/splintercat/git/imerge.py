"""Wrapper around git-imerge library."""

import os
from contextlib import suppress
from pathlib import Path

import gitimerge

from splintercat.core.log import logger
from splintercat.core.runner import Runner
from splintercat.git.shim import capture_gitimerge_output


class IMerge:
    """Wrapper for git-imerge operations using the Python API."""

    def __init__(
        self, workdir: Path, name: str, goal: str = "merge", config=None
    ):
        """Initialize git-imerge wrapper.

        Args:
            workdir: Path to git repository
            name: Name for this imerge operation
            goal: Merge goal (merge, rebase, etc.)
            config: Configuration object with commands templates
        """
        self.workdir = workdir
        self.name = name
        self.goal = goal
        self.config = config
        self.git = None
        self.merge_state = None

        # Change to workdir for git operations
        self._original_dir = os.getcwd()
        os.chdir(str(workdir))
        self.git = gitimerge.GitRepository()
        self.runner = Runner()

    @classmethod
    def exists(cls, workdir: Path, name: str) -> bool:
        """Check if an imerge with given name exists.

        Args:
            workdir: Path to git repository
            name: Name of imerge to check

        Returns:
            True if imerge exists, False otherwise
        """
        original_dir = os.getcwd()
        try:
            os.chdir(str(workdir))
            git = gitimerge.GitRepository()
            return git.check_imerge_exists(name)
        finally:
            os.chdir(original_dir)

    def load_existing(self):
        """Load existing imerge state instead of starting new merge.

        Cleans up any pending merge from previous interrupted
        session before loading state.

        Raises:
            ValueError: If imerge does not exist
        """
        if not self.git:
            raise ValueError("GitRepository not initialized")

        # Clean up any pending merge from previous interrupted
        # session
        # This is equivalent to "git merge --abort" that git-imerge
        # docs recommend
        if self.config:
            with suppress(Exception):
                cmd = self.config.commands["git"]["merge_abort"]
                self.runner.execute(
                    cmd,
                    cwd=self.workdir,
                    check=False,  # Don't error if no merge
                )

            # If merge --abort fails, try reset --merge
            with suppress(Exception):
                cmd = self.config.commands["git"]["reset_merge"]
                self.runner.execute(
                    cmd,
                    cwd=self.workdir,
                    check=False,
                )

        with capture_gitimerge_output():
            self.merge_state = gitimerge.MergeState.read(
                self.git, self.name
            )

    def start_merge(self, source_ref: str, target_branch: str):
        """Start an incremental merge.

        Args:
            source_ref: Source git ref to merge from
            target_branch: Target branch to merge into
        """
        with capture_gitimerge_output():
            # Require clean work tree
            self.git.require_clean_work_tree('proceed')

            # Get merge boundaries
            # (returns merge_base, commits1, commits2)
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
            Tuple of (i1, i2) for next conflict, or None if no
                conflicts
        """
        if not self.merge_state:
            return None

        with capture_gitimerge_output():
            try:
                # Auto-complete what we can
                self.merge_state.auto_complete_frontier()
            except gitimerge.FrontierBlockedError as e:
                # Found a conflict - extract (i1, i2) from
                # blocked frontier
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
        with capture_gitimerge_output():
            # Request user merge for this conflict pair
            self.merge_state.request_user_merge(i1, i2)

        # Get conflicted files from git status
        if self.config:
            cmd = self.config.commands["git"]["diff_conflicted_files"]
        else:
            cmd = "git diff --name-only --diff-filter=U"
        result = self.runner.execute(
            cmd,
            cwd=self.workdir,
            check=False,
        )
        output = result.stdout.strip()
        return output.split("\n") if output else []

    def read_conflicted_file(self, filepath: str) -> str:
        """Read a file with conflict markers from working tree.

        Args:
            filepath: Path to file relative to workdir

        Returns:
            File content with conflict markers

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = self.workdir / filepath
        return file_path.read_text()

    def write_resolution(self, filepath: str, content: str):
        """Write resolved content to file in working tree.

        Args:
            filepath: Path to file relative to workdir
            content: Resolved content (no conflict markers)
        """
        file_path = self.workdir / filepath
        file_path.write_text(content)

    def stage_file(self, filepath: str):
        """Stage a resolved file with git add.

        Handles expected failures gracefully:
        - File already staged (e.g., by git rm) -> Success
        - Other failures -> Raise with clear error message

        Args:
            filepath: Path to file relative to workdir

        Raises:
            RuntimeError: If staging fails for unexpected reason
        """
        if self.config:
            cmd = self.config.commands["git"]["add_file"].format(
                filepath=filepath
            )
        else:
            cmd = f"git add {filepath}"

        result = self.runner.execute(
            cmd,
            cwd=self.workdir,
            check=False,  # Don't raise, we'll inspect the result
        )

        if result.exited == 0:
            logger.debug(f"Staged {filepath}")
            return

        # Check if this is expected (file already staged by git rm)
        if "did not match any files" in result.stderr:
            logger.info(
                f"File {filepath} already staged "
                f"(likely deleted with git rm)"
            )
            return

        # Unexpected error - provide clear message with full context
        raise RuntimeError(
            f"Failed to stage {filepath}: exit code {result.exited}\n"
            f"Command: {cmd}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )

    def continue_after_resolution(self):
        """Continue merge after user has resolved conflicts."""
        if not self.merge_state:
            return

        with capture_gitimerge_output():
            # Incorporate the user's manual merge
            self.merge_state.incorporate_user_merge()
            self.merge_state.save()

    def is_complete(self) -> bool:
        """Check if merge is complete.

        Returns:
            True if all conflicts resolved and ready to
                finalize
        """
        if not self.merge_state:
            return False

        with capture_gitimerge_output():
            try:
                self.merge_state.auto_complete_frontier()
                return True
            except (
                gitimerge.FrontierBlockedError,
                gitimerge.NothingToDoError
            ):
                return False

    def finalize(self) -> str:
        """Simplify merge to single two-parent merge commit.

        Returns:
            SHA of final merge commit
        """
        if not self.merge_state:
            raise ValueError("No merge state to finalize")

        with capture_gitimerge_output():
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
