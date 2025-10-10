"""Graph workflow definition."""

from pydantic_graph import Graph

from src.core.config import Settings
from src.core.log import logger
from src.state.workflow import MergeWorkflowState


def create_workflow(settings: Settings):
    """Create the merge workflow graph.

    Args:
        settings: Application configuration

    Returns:
        Graph workflow
    """
    logger.debug("Building workflow graph")

    # Import nodes (lazy to avoid circular imports)
    # All converted to BaseNode dataclasses
    from src.workflow.nodes.build_test import Build, Tests
    from src.workflow.nodes.execute_recovery import ExecuteRecovery
    from src.workflow.nodes.finalize import Finalize
    from src.workflow.nodes.initialize import Initialize
    from src.workflow.nodes.plan_recovery import PlanRecovery
    from src.workflow.nodes.plan_strategy import PlanStrategy
    from src.workflow.nodes.resolve_conflicts import ResolveConflicts
    from src.workflow.nodes.summarize_failure import SummarizeFailure

    # Create graph with pydantic-graph API
    workflow = Graph(
        nodes=(
            Initialize,
            PlanStrategy,
            ResolveConflicts,
            Build,
            Tests,
            SummarizeFailure,
            PlanRecovery,
            ExecuteRecovery,
            Finalize,
        ),
        state_type=MergeWorkflowState
    )

    return workflow
