"""PlanRecovery node - planner analyzes failure and decides next steps."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.state.workflow import MergeWorkflowState


@dataclass
class PlanRecovery(BaseNode[MergeWorkflowState]):
    """Planner analyzes failure and decides next recovery strategy."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> ExecuteRecovery:
        """Analyze failure and decide recovery approach.

        Returns:
            ExecuteRecovery: Next node to execute recovery strategy
        """
        pass

# Backward compatibility
plan_recovery = PlanRecovery
