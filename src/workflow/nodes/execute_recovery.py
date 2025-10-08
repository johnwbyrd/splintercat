"""ExecuteRecovery node - apply recovery strategy based on planner decision."""

from src.state.workflow import MergeWorkflowState


def execute_recovery(state: MergeWorkflowState) -> MergeWorkflowState:
    """Execute recovery strategy based on planner's decision.

    Uses recovery classes (retry_all, retry_specific, bisect, switch_strategy)
    to apply the chosen recovery approach.

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with recovery applied
    """
    pass
