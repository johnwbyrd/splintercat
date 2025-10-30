"""Reset command - cleans git-imerge state."""

from pydantic import BaseModel, Field

from splintercat.core.log import logger


class ResetCommand(BaseModel):
    """Clean up git-imerge state and reset repository to known good state.

    Removes all git-imerge refs and state, aborts any in-progress merge,
    cleans working directory, and recreates target branch from source.
    This provides a complete reset to a known good state, equivalent to
    the reset-branches.bash script.
    """

    destroy_target_branch: bool = Field(
        default=True,
        alias="destroy-target-branch",
        description=(
            "Destroy and recreate target branch from source ref (default behavior). "
            "Use --destroy-target-branch=false for safe reset that preserves branch. "
            "Steps: (1) abort any in-progress merge, (2) hard reset "
            "working tree, (3) clean untracked files, (4) delete "
            "target branch, (5) checkout -B target from source"
        )
    )

    async def run_workflow(self, state: "State") -> int:
        """Run reset workflow.

        Args:
            state: State instance

        Returns:
            Exit code (0=success)
        """
        # Set flags on reset state
        state.runtime.reset.destroy_target_branch = (
            self.destroy_target_branch
        )

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
