"""Finalize node - simplify merge to single commit and clean up."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from splintercat.core.config import State


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
        # TODO: Implement git-imerge finalization
        # For now, just end the workflow
        ctx.state.runtime.merge.status = "complete"
        return End("mock-final-commit-sha")

# Backward compatibility
finalize = Finalize
