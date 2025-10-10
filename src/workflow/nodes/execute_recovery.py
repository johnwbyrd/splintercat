"""ExecuteRecovery node - apply recovery strategy based on planner decision."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.state.workflow import MergeWorkflowState


@dataclass
class ExecuteRecovery(BaseNode[MergeWorkflowState]):
    """Apply recovery strategy based on planner's decision."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> ResolveConflicts:
        """Execute chosen recovery strategy and resume workflow.

        Returns:
            ResolveConflicts: Resume conflict resolution after recovery
        """
        pass

# Backward compatibility
execute_recovery = ExecuteRecovery
