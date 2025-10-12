"""ResolveConflicts node - resolve conflicts using resolver model."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger


@dataclass
class ResolveConflicts(BaseNode[State]):
    """Resolve conflicts using resolver model."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "Check":
        """Resolve conflicts using resolver model.

        Returns:
            Check: Next node to run checks
        """
        logger.info("ResolveConflicts node - stub implementation")
        # TODO: Implement conflict resolution logic
        # For now, assume no conflicts and go to checks
        ctx.state.runtime.merge.conflicts_remaining = False

        from splintercat.workflow.nodes.check import Check
        return Check(check_names=["quick"])

# Backward compatibility
resolve_conflicts = ResolveConflicts
