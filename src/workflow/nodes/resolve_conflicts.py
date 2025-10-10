"""ResolveConflicts node - resolve conflicts using resolver model."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.config import State


@dataclass
class ResolveConflicts(BaseNode[State]):
    """Resolve conflicts using resolver model."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "Build":
        """Resolve conflicts using resolver model.

        Returns:
            Build: Next node to run build/test
        """
        # TODO: Implement conflict resolution logic
        # For now, just return next node
        from src.workflow.nodes.build_test import Build
        return Build()

# Backward compatibility
resolve_conflicts = ResolveConflicts
