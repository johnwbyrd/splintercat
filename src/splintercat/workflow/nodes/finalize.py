"""Finalize node - simplify merge to single commit and clean up."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger


@dataclass
class Finalize(BaseNode[State, None, str]):
    """Simplify merge to single commit and clean up git-imerge state."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> End[str]:
        """Complete merge by creating final commit and cleaning up.

        Returns:
            End[str]: Workflow completion with final commit SHA
        """
        imerge = ctx.state.runtime.merge.current_imerge
        if not imerge:
            raise ValueError("No active imerge to finalize")

        logger.info("Finalizing merge - simplifying to single commit")

        # Call git-imerge finalize to create final merge commit
        final_commit = imerge.finalize()

        # Update state
        ctx.state.runtime.merge.status = "complete"

        logger.info(f"Merge complete! Final commit: {final_commit}")
        return End(final_commit)
