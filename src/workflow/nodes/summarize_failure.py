"""SummarizeFailure node - extract error info from failed build logs."""

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.state.workflow import MergeWorkflowState


@dataclass
class SummarizeFailure(BaseNode[MergeWorkflowState]):
    """Extract error information from failed build logs using summarizer model."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> "PlanRecovery":
        """Analyze failure logs and extract error information.

        Returns:
            PlanRecovery: Next node to plan recovery strategy
        """
        pass

# Backward compatibility
summarize_failure = SummarizeFailure
