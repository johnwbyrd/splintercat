"""ExecuteRecovery node - apply recovery strategy based on
planner decision."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger


@dataclass
class ExecuteRecovery(BaseNode[State]):
    """Apply recovery strategy based on planner's decision."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "ResolveConflicts":
        """Execute chosen recovery strategy and resume workflow.

        Returns:
            ResolveConflicts: Resume conflict resolution after recovery
        """
        # Increment recovery attempt counter
        ctx.state.runtime.merge.recovery_attempts += 1
        logger.info(
            f"Executing recovery attempt "
            f"{ctx.state.runtime.merge.recovery_attempts}"
        )

        # TODO: Implement recovery execution logic
        from splintercat.workflow.nodes.resolve_conflicts import (
            ResolveConflicts,
        )
        return ResolveConflicts()

# Backward compatibility
execute_recovery = ExecuteRecovery
