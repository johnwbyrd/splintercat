"""SummarizeFailure node - extract error info from failed build logs."""

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.config import State


@dataclass
class SummarizeFailure(BaseNode[State]):
    """Extract error information from failed build logs using
    summarizer model."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "PlanRecovery":
        """Analyze failure logs and extract error information.

        Returns:
            PlanRecovery: Next node to plan recovery strategy
        """
        # TODO: Implement summarization logic
        from src.workflow.nodes.plan_recovery import PlanRecovery

        return PlanRecovery()

# Backward compatibility
summarize_failure = SummarizeFailure
