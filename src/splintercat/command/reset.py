"""Reset command - cleans git-imerge state."""

from pydantic import BaseModel, Field

from splintercat.core.log import logger


class ResetCommand(BaseModel):
    """Clean up git-imerge state and abort current merge.

    Removes all git-imerge refs and state, effectively aborting any
    in-progress merge operation. This is useful for starting fresh or
    cleaning up after a failed merge.
    """

    force: bool = Field(
        default=False,
        description="Skip confirmation prompt and delete immediately"
    )

    async def run_workflow(self, state: "State") -> int:
        """Run reset workflow.

        Args:
            state: State instance

        Returns:
            Exit code (0=success)
        """
        # Set force flag on reset state
        state.runtime.reset.force = self.force

        # Set current command
        state.runtime.global_.current_command = "reset"

        # Create single-node workflow
        from pydantic_graph import Graph

        from splintercat.workflow.nodes.reset import Reset

        workflow = Graph(nodes=(Reset,), state_type=type(state))

        # Run workflow (just the Reset node)
        async with workflow.iter(Reset(), state=state) as run:
            async for _node in run:
                pass  # Reset node doesn't return data

        logger.info("Reset complete")
        return 0
