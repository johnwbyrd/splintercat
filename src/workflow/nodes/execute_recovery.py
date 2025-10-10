"""ExecuteRecovery node - apply recovery strategy based on planner decision."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.config import State


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
        # TODO: Implement recovery execution logic
        from src.workflow.nodes.resolve_conflicts import ResolveConflicts
        return ResolveConflicts()

# Backward compatibility
execute_recovery = ExecuteRecovery
