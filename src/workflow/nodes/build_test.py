"""BuildTest node - run build/test command and capture output."""

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.state.workflow import MergeWorkflowState


@dataclass
class Tests(BaseNode[MergeWorkflowState]):
    """Run test command and determine success/failure."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> "Finalize":
        """Execute test command and check result.

        Returns:
            Finalize: Simplified - assume tests pass and finalize
        """
        # TODO: Implement test logic and conditional routing
        # For now, assume success and go to finalize
        from src.workflow.nodes.finalize import Finalize
        return Finalize()

@dataclass
class Build(BaseNode[MergeWorkflowState]):
    """Run build command and determine success/failure."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> "Tests":
        """Execute build command and check result.

        Returns:
            Tests: Next node to run test command
        """
        # TODO: Implement build logic
        # For now, just return next node
        return Tests()

# Backward compatibility
build_node = Build
run_tests = Tests
