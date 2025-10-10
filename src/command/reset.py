"""Reset command - cleans git-imerge state."""

from pydantic import BaseModel

from src.core.log import logger


class ResetCommand(BaseModel):
    """Clean git-imerge state.

    Parameters:
        force: Skip confirmation prompt if True
    """

    force: bool = False

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

        from src.workflow.nodes.reset import Reset

        workflow = Graph(nodes=(Reset,), state_type=type(state))

        # Run workflow (just the Reset node)
        async with workflow.iter(Reset(), state=state) as run:
            async for _node in run:
                pass  # Reset node doesn't return data

        logger.info("Reset complete")
        return 0
