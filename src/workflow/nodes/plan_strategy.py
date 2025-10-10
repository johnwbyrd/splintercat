"""PlanStrategy node - planner chooses merge strategy."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.state.workflow import MergeWorkflowState


@dataclass
class PlanStrategy(BaseNode[MergeWorkflowState]):
    """Planner chooses initial merge strategy and parameters."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> "ResolveConflicts":
        """Choose merge strategy and create strategy instance.

        Returns:
            ResolveConflicts: Next node to start conflict resolution
        """
        # TODO: Implement strategy planning logic
        # For now, just return next node
        from src.workflow.nodes.resolve_conflicts import ResolveConflicts
        return ResolveConflicts()
