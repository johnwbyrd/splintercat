"""PlanRecovery node - planner analyzes failure and decides next steps."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.config import State


@dataclass
class PlanRecovery(BaseNode[State]):
    """Planner analyzes failure and decides next recovery strategy."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "ExecuteRecovery":
        """Analyze failure and decide recovery approach.

        Returns:
            ExecuteRecovery: Next node to execute recovery strategy
        """
        # TODO: Implement recovery planning logic
        from src.workflow.nodes.execute_recovery import ExecuteRecovery
        return ExecuteRecovery()

# Backward compatibility
plan_recovery = PlanRecovery
