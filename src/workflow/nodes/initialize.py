"""Initialize node - start git-imerge and set up initial state."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.state.workflow import MergeWorkflowState


@dataclass
class Initialize(BaseNode[MergeWorkflowState]):
    """Initialize git-imerge merge and set up initial workflow state."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> "PlanStrategy":
        """Start git-imerge merge and initialize workflow state.

        Returns:
            PlanStrategy: Next node to choose merge strategy
        """
        # TODO: Implement git-imerge initialization logic
        # For now, just return next node
        from src.workflow.nodes.plan_strategy import PlanStrategy
        return PlanStrategy()
