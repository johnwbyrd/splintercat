"""PlanRecovery node - planner analyzes failure and decides
next steps."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger


@dataclass
class PlanRecovery(BaseNode[State, None, str]):
    """Planner analyzes failure and decides next recovery strategy."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "ExecuteRecovery | End[str]":
        """Analyze failure and decide recovery approach.

        Returns:
            ExecuteRecovery: Next node to execute recovery strategy
            End[str]: If max retries exceeded, abort with error message
        """
        # Check if we've exceeded max retries
        max_retries = ctx.state.config.strategy.max_retries
        current_attempts = ctx.state.runtime.merge.recovery_attempts

        logger.info(
            f"Recovery attempt {current_attempts + 1} of "
            f"{max_retries}"
        )

        if current_attempts >= max_retries:
            logger.error(
                f"Max retries ({max_retries}) exceeded. "
                f"Aborting merge."
            )
            ctx.state.runtime.merge.status = "failed"
            return End(
                f"Merge failed after {max_retries} recovery attempts"
            )

        # TODO: Implement recovery planning logic
        from splintercat.workflow.nodes.execute_recovery import ExecuteRecovery
        return ExecuteRecovery()

# Backward compatibility
plan_recovery = PlanRecovery
