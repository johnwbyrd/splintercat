"""BuildTest node - run build/test command and capture output."""

from src.state.workflow import MergeWorkflowState


def build_node(state: MergeWorkflowState) -> MergeWorkflowState:
    """Run build command, save logs, determine success/failure.

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with build result
    """
    pass


def run_tests(state: MergeWorkflowState) -> MergeWorkflowState:
    """Run test command, save logs, determine success/failure.

    Args:
        state: Current workflow state

    Returns:
        Updated workflow state with test result
    """
    pass
