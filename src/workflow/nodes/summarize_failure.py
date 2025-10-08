"""SummarizeFailure node - extract error info from failed build logs."""

from src.state.workflow import MergeWorkflowState


def summarize_failure(state: MergeWorkflowState) -> MergeWorkflowState:
    """Extract error information from failed build logs using summarizer model.

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with failure summary
    """
    pass
