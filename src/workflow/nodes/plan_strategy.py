"""PlanStrategy node - planner chooses merge strategy."""

from src.state.workflow import MergeWorkflowState


def plan_strategy(state: MergeWorkflowState) -> MergeWorkflowState:
    """Planner chooses initial merge strategy and parameters.

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with chosen strategy
    """
    pass
