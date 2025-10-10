"""Reset node - discard all git-imerge state."""

from __future__ import annotations
from pathlib import Path
import subprocess
from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.log import logger
from src.state.workflow import MergeWorkflowState


@dataclass
class Reset(BaseNode[MergeWorkflowState]):
    """Reset (discard) all git-imerge state for a merge operation."""

    force: bool = False

    async def run(self, ctx: GraphRunContext[MergeWorkflowState]):
        """Reset all git-imerge state, returning repository to clean state."""

        workdir = ctx.state.settings.target.workdir

        # Get existing merge names
        existing_merges = self._get_existing_merges(workdir)
        if not existing_merges:
            logger.warning("No git-imerge merges found to reset")
            return

        logger.info(f"Found existing merges: {', '.join(existing_merges)}")

        # Show what will be reset
        total_refs = 0
        for merge_name in existing_merges:
            refs = self._get_merge_refs(workdir, merge_name)
            total_refs += len(refs)
            logger.info(f"  {merge_name}: {len(refs)} refs")

        # Confirm unless force is set
        if not self.force:
            if not await self._confirm_reset(total_refs):
                logger.info("Reset cancelled by user")
                return

        # Perform reset
        logger.info(f"Resetting {total_refs} refs from {len(existing_merges)} merges...")
        self._reset_all_merges(workdir, existing_merges)

        # Update state
        ctx.state.imerge = None
        ctx.state.imerge_name = None
        ctx.state.status = "reset"

        logger.info("Git repository reset complete - all imerge state discarded")

    def _get_existing_merges(self, workdir: str) -> list[str]:
        """Get list of all existing imerge merge names."""
        try:
            cmd = ["git", "for-each-ref", "--format=%(refname:short)", "refs/imerge"]
            result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, check=True)
            # Extract unique merge names from refs/imerge/NAME/...
            lines = result.stdout.strip().split('\n')
            names = set()
            for line in lines:
                if line.startswith('refs/imerge/'):
                    # Format: refs/imerge/NAME/...
                    parts = line.split('/')
                    if len(parts) >= 3:
                        names.add(parts[2])
            return sorted(list(names))
        except subprocess.CalledProcessError:
            return []

    def _get_merge_refs(self, workdir: str, merge_name: str) -> list[str]:
        """Get all refs for a specific merge."""
        try:
            cmd = ["git", "for-each-ref", "--format=%(refname)", f"refs/imerge/{merge_name}/**"]
            result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, check=True)
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        except subprocess.CalledProcessError:
            return []

    async def _confirm_reset(self, total_refs: int) -> bool:
        """Get user confirmation for reset operation."""
        # TODO: Implement interactive confirmation
        # For now, show warning and assume cancelled for safety
        logger.warning("Interactive confirmation not implemented - reset cancelled for safety")
        logger.warning("Use 'splintercat reset --force' to force reset without confirmation")
        return False

    def _reset_all_merges(self, workdir: str, merge_names: list[str]):
        """Reset all imerge state by deleting all refs."""
        all_refs = []
        for merge_name in merge_names:
            refs = self._get_merge_refs(workdir, merge_name)
            all_refs.extend(refs)

        if not all_refs:
            return

        # Use git update-ref --stdin for efficient bulk deletion
        delete_commands = [f"delete {ref}" for ref in all_refs]
        input_data = '\n'.join(delete_commands) + '\n'

        cmd = ["git", "update-ref", "--stdin"]
        subprocess.run(cmd, cwd=workdir, input=input_data, text=True, check=True)

        logger.info(f"Deleted {len(all_refs)} imerge refs")
