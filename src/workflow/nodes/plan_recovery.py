"""PlanRecovery node - planner analyzes failure and decides next steps."""

from src.state.workflow import MergeWorkflowState


def plan_recovery(state: MergeWorkflowState) -> MergeWorkflowState:
    """Planner analyzes failure and returns routing decision.

    Returns decision about next action:
    - retry (retry-all or retry-specific)
    - bisect
    - switch-strategy
    - abort

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with recovery decision
    """
    pass
