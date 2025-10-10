"""Graph workflow definition."""

from pydantic_graph import Graph

from src.core.config import State
from src.core.log import logger


def create_workflow():
    """Create the merge workflow graph.

    Returns:
        Graph workflow with State as state_type
    """
    logger.debug("Building workflow graph")

    # Import nodes (lazy to avoid circular imports)
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
        state_type=State
    )

    return workflow
