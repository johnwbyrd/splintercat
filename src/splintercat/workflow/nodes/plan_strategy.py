"""PlanStrategy node - planner chooses merge strategy."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger


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
        logger.info("PlanStrategy node - stub implementation")
        # TODO: Implement strategy planning logic
        # For now, just return next node
        from splintercat.workflow.nodes.resolve_conflicts import (
            ResolveConflicts,
        )
        return ResolveConflicts()
