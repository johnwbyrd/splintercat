"""PlanStrategy node - planner chooses merge strategy."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.config import State


@dataclass
class PlanStrategy(BaseNode[State]):
    """Planner chooses initial merge strategy and parameters."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "ResolveConflicts":
        """Choose merge strategy and create strategy instance.

        Returns:
            ResolveConflicts: Next node to start conflict resolution
        """
        # TODO: Implement strategy planning logic
        # For now, just return next node
        from src.workflow.nodes.resolve_conflicts import ResolveConflicts
        return ResolveConflicts()
