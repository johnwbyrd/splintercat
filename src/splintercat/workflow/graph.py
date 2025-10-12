"""Graph workflow definition."""

from pydantic_graph import Graph

from splintercat.core.config import State
from splintercat.core.log import logger


def create_workflow():
    """Create the merge workflow graph.

    Returns:
        Graph workflow with State as state_type
    """
    logger.debug("Building workflow graph")

    # Import nodes (lazy to avoid circular imports)
    from splintercat.workflow.nodes.check import Check
    from splintercat.workflow.nodes.execute_recovery import ExecuteRecovery
    from splintercat.workflow.nodes.finalize import Finalize
    from splintercat.workflow.nodes.initialize import Initialize
    from splintercat.workflow.nodes.plan_recovery import PlanRecovery
    from splintercat.workflow.nodes.plan_strategy import PlanStrategy
    from splintercat.workflow.nodes.resolve_conflicts import ResolveConflicts
    from splintercat.workflow.nodes.summarize_failure import SummarizeFailure

    # Create graph with pydantic-graph API
    workflow = Graph(
        nodes=(
            Initialize,
            PlanStrategy,
            ResolveConflicts,
            Check,
            SummarizeFailure,
            PlanRecovery,
            ExecuteRecovery,
            Finalize,
        ),
        state_type=State
    )

    return workflow
