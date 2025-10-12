"""ResolveConflicts node - resolve conflicts using resolver model."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger


@dataclass
class ResolveConflicts(BaseNode[State]):
    """Resolve conflicts using resolver model and strategy."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "Check":
        """Resolve conflicts in current batch using resolver model.

        Uses the active strategy to determine batch size and
        when to check. Retries use error context from last failed check.

        Returns:
            Check: Next node to run checks after resolving batch
        """
        logger.info("ResolveConflicts node - stub implementation")

        # TODO: Implement conflict resolution logic:
        # 1. Get strategy from ctx.state.runtime.merge.strategy
        # 2. Get conflicts from imerge.get_current_conflict()
        # 3. Resolve until strategy.should_check_now() is True
        # 4. If retry_count > 0, pass error from last_failed_check
        # 5. Update conflicts_remaining from imerge state
        # 6. Return Check with appropriate check_names

        # Stub: assume no conflicts remain
        ctx.state.runtime.merge.conflicts_remaining = False

        from splintercat.workflow.nodes.check import Check
        # TODO: Determine which checks to run based on strategy
        return Check(check_names=["quick"])
