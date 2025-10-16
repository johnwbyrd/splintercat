"""Reset node - discard all git-imerge state."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger
from splintercat.core.runner import Runner


@dataclass
class Reset(BaseNode[State]):
    """Reset (discard) all git-imerge state for a merge
    operation."""

    async def run(self, ctx: GraphRunContext[State]) -> End[None]:
        """Reset all git-imerge state, returning repository to
        clean state.

        Returns:
            End[None]: Workflow completion with no data
        """
        workdir = ctx.state.config.git.target_workdir
        destroy_branch = ctx.state.runtime.reset.destroy_target_branch
        runner = Runner()

        # If destroy_target_branch is set, do full branch recreation
        if destroy_branch:
            self._destroy_and_recreate_branch(runner, workdir, ctx.state)
            logger.info("Target branch destroyed and recreated from source")
            return End(None)

        # Get existing merge names
        existing_merges = self._get_existing_merges(runner, workdir, ctx.state)
        if not existing_merges:
            logger.warning("No git-imerge merges found to reset")
            return End(None)

        logger.info(f"Found existing merges: {', '.join(existing_merges)}")

        # Perform reset - deletes all imerge refs in one atomic
        # operation
        self._reset_all_merges(runner, workdir, ctx.state)

        # Update state
        ctx.state.runtime.reset.merge_names_found = existing_merges
        ctx.state.runtime.reset.status = "complete"
        ctx.state.runtime.merge.current_imerge = None

        logger.info(
            "Git repository reset complete - all imerge state "
            "discarded"
        )
        return End(None)

    def _get_existing_merges(
        self, runner: Runner, workdir, state: State
    ) -> list[str]:
        """Get list of all existing imerge merge names."""
        logger.info(f"Looking for imerge refs in: {workdir}")
        try:
            cmd = state.config.commands["git"]["for_each_ref_list"]
            result = runner.execute(
                cmd.format(refspec="refs/imerge"),
                cwd=workdir,
                check=True,
            )
            logger.debug(
                f"Git command stdout length: {len(result.stdout)} chars"
            )
            logger.debug(
                f"Git command output (first 500 chars): "
                f"{result.stdout[:500]}"
            )

            # Extract unique merge names from imerge/NAME/...
            # Note: refname:short format gives "imerge/NAME/..."
            # not "refs/imerge/NAME/..."
            lines = result.stdout.strip().split('\n')
            logger.debug(f"Found {len(lines)} ref lines")

            names = set()
            for line in lines:
                if line.startswith('imerge/'):
                    # Format: imerge/NAME/...
                    parts = line.split('/')
                    if len(parts) >= 2:
                        names.add(parts[1])

            logger.info(
                f"Found {len(names)} unique merge names: "
                f"{sorted(names)}"
            )
            return sorted(names)
        except Exception as e:
            logger.error(f"Failed to get existing merges: {e}")
            return []

    def _get_merge_refs(
        self,
        runner: Runner,
        workdir,
        merge_name: str,
        state: State,
    ) -> list[str]:
        """Get all refs for a specific merge."""
        logger.debug(f"Getting refs for merge: {merge_name}")
        try:
            # Use prefix matching, not glob - git for-each-ref
            # matches all refs with this prefix
            cmd = state.config.commands["git"]["for_each_ref_by_prefix"]
            result = runner.execute(
                cmd.format(refspec=f"refs/imerge/{merge_name}/"),
                cwd=workdir,
                check=True,
            )
            refs = [
                line.strip()
                for line in result.stdout.strip().split('\n')
                if line.strip()
            ]
            logger.debug(f"Found {len(refs)} refs for {merge_name}")
            return refs
        except Exception as e:
            logger.error(f"Failed to get refs for {merge_name}: {e}")
            return []

    async def _confirm_reset(self, num_merges: int) -> bool:
        """Get user confirmation for reset operation."""
        # TODO: Implement interactive confirmation
        # For now, show warning and assume cancelled for safety
        logger.warning(
            "Interactive confirmation not implemented - reset "
            "cancelled for safety"
        )
        logger.warning(
            f"Would delete all refs from {num_merges} imerge "
            f"merge(s)"
        )
        logger.warning(
            "Use 'reset --force' subcommand to force "
            "reset without confirmation"
        )
        return False

    def _reset_all_merges(self, runner: Runner, workdir, state: State):
        """Reset all imerge state by deleting all refs.

        Uses git pipeline approach from Stack Overflow:
        https://stackoverflow.com/questions/46229291/
        in-git-how-can-i-efficiently-delete-all-refs-matching-
        a-pattern

        The command 'git for-each-ref --format="delete
        %(refname)" refs/imerge/' generates delete commands for
        each ref, which are piped to 'git update-ref --stdin'
        for atomic bulk deletion.
        """
        logger.info("Deleting all imerge refs via git pipeline")

        # Single pipeline command to delete all imerge refs
        # atomically. format='delete %(refname)' generates:
        # delete refs/imerge/name/path. These are piped to
        # update-ref --stdin which executes all deletions
        # together
        cmd = state.config.commands["git"]["for_each_ref_delete"]
        runner.execute(
            cmd.format(refspec="refs/imerge/"),
            cwd=workdir,
            check=True,
        )

        logger.info("Successfully deleted all imerge refs")

    def _destroy_and_recreate_branch(
        self, runner: Runner, workdir, state: State
    ):
        """Destroy target branch and recreate from source ref.

        Performs a complete reset of the target branch:
        1. Abort any in-progress merge operation
        2. Discard all uncommitted changes (hard reset)
        3. Remove all untracked files and directories
        4. Delete the target branch entirely
        5. Create fresh target branch from source ref

        This is a destructive operation that cannot be undone.
        """
        target = state.config.git.target_branch
        source = state.config.git.source_ref
        logger.info(
            f"Destroying {target} and recreating from {source}"
        )

        # Abort any in-progress merge (e.g., git merge, git imerge)
        logger.info("Aborting any in-progress merge...")
        runner.execute(
            "git merge --abort", cwd=workdir, check=False
        )

        # Discard all changes in working tree and staging area
        logger.info("Hard resetting working tree...")
        runner.execute("git reset --hard", cwd=workdir, check=True)

        # Remove all untracked files and directories
        logger.info("Cleaning untracked files...")
        runner.execute("git clean -fd", cwd=workdir, check=True)

        # Delete target branch (fails silently if doesn't exist)
        logger.info(f"Deleting branch {target}...")
        runner.execute(
            f"git branch -D {target}", cwd=workdir, check=False
        )

        # Create target branch from source ref (or reset if exists)
        logger.info(f"Creating {target} from {source}...")
        runner.execute(
            f"git checkout -B {target} {source}",
            cwd=workdir,
            check=True,
        )

        logger.info(f"Branch {target} recreated successfully")
