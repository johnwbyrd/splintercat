"""LangGraph workflow definition."""

from langgraph.graph import END, StateGraph

from src.core.config import Settings
from src.core.log import logger
from src.state.workflow import MergeWorkflowState


def create_workflow(settings: Settings):
    """Create the merge workflow graph.

    Args:
        settings: Application configuration

    Returns:
        Compiled LangGraph workflow
    """
    logger.debug("Building workflow graph")

    # Import nodes (lazy to avoid circular imports)
    from src.workflow.nodes.build_test import build_node, test_node
    from src.workflow.nodes.execute_recovery import execute_recovery
    from src.workflow.nodes.finalize import finalize
    from src.workflow.nodes.initialize import initialize
    from src.workflow.nodes.plan_recovery import plan_recovery
    from src.workflow.nodes.plan_strategy import plan_strategy
    from src.workflow.nodes.resolve_conflicts import resolve_conflicts
    from src.workflow.nodes.summarize_failure import summarize_failure

    # Build graph
    workflow = StateGraph(MergeWorkflowState)

    # Add nodes
    workflow.add_node("initialize", initialize)
    workflow.add_node("plan_strategy", plan_strategy)
    workflow.add_node("resolve_conflicts", resolve_conflicts)
    workflow.add_node("build", build_node)
    workflow.add_node("test", test_node)
    workflow.add_node("summarize_failure", summarize_failure)
    workflow.add_node("plan_recovery", plan_recovery)
    workflow.add_node("execute_recovery", execute_recovery)
    workflow.add_node("finalize", finalize)

    # Define edges
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "plan_strategy")
    workflow.add_edge("plan_strategy", "resolve_conflicts")

    # After resolving conflicts, build
    workflow.add_edge("resolve_conflicts", "build")

    # After build: conditional routing
    workflow.add_conditional_edges(
        "build",
        _after_build,
        {
            "test": "test",
            "resolve_conflicts": "resolve_conflicts",
            "summarize_failure": "summarize_failure",
        }
    )

    # After test: conditional routing
    workflow.add_conditional_edges(
        "test",
        _after_test,
        {
            "finalize": "finalize",
            "resolve_conflicts": "resolve_conflicts",
            "summarize_failure": "summarize_failure",
        }
    )

    workflow.add_edge("summarize_failure", "plan_recovery")

    # After recovery planning: conditional routing
    workflow.add_conditional_edges(
        "plan_recovery",
        _after_recovery_plan,
        {
            "execute_recovery": "execute_recovery",
            "plan_strategy": "plan_strategy",
            END: END,
        }
    )

    workflow.add_edge("execute_recovery", "resolve_conflicts")
    workflow.add_edge("finalize", END)

    return workflow.compile()


def _after_build(state: MergeWorkflowState) -> str:
    """Route after build node.

    Args:
        state: Current state

    Returns:
        Next node name
    """
    build_result = getattr(state, "build_result", None)

    if not build_result or not build_result.success:
        return "summarize_failure"

    # Build passed - run tests
    return "test"


def _after_test(state: MergeWorkflowState) -> str:
    """Route after test node.

    Args:
        state: Current state

    Returns:
        Next node name
    """
    test_result = getattr(state, "test_result", None)

    if not test_result or not test_result.success:
        return "summarize_failure"

    # Tests passed - check if more conflicts
    if getattr(state, "conflicts_remaining", False):
        return "resolve_conflicts"

    # All done
    return "finalize"


def _after_recovery_plan(state: MergeWorkflowState) -> str:
    """Route after recovery planning.

    Args:
        state: Current state

    Returns:
        Next node name
    """
    decision = getattr(state, "recovery_decision", None)

    if not decision:
        return END

    if decision.decision == "abort":
        return END
    elif decision.decision == "switch_strategy":
        return "plan_strategy"
    else:
        return "execute_recovery"
