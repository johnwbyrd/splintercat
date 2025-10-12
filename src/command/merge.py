"""Merge command - runs the merge workflow."""

from pydantic import BaseModel

from src.core.log import logger


class MergeCommand(BaseModel):
    """Run LLM-assisted incremental merge with build validation.

    Performs git-imerge merge with conflict resolution using LLM models,
    validates each step with build/test checks, and implements smart
    recovery strategies when failures occur.

    All configuration comes from config.yaml, .env, or CLI flags.
    """

    async def run_workflow(self, state: "State") -> int:
        """Run merge workflow.

        Args:
            state: State instance with config loaded and runtime initialized

        Returns:
            Exit code (0=success, 1=failure)
        """
        logger.info(
            f"Starting merge of {state.config.git.source_ref} "
            f"into {state.config.git.target_branch}"
        )

        # Set current command in global state
        state.runtime.global_.current_command = "merge"

        # Create workflow graph
        from src.workflow.graph import create_workflow
        from src.workflow.nodes.initialize import Initialize

        workflow = create_workflow()

        # Run workflow starting at Initialize node
        async with workflow.iter(Initialize(), state=state) as run:
            async for node in run:
                if hasattr(node, 'data'):
                    # End node reached with final data
                    logger.info(f"Merge complete! Final commit: {node.data}")
                    return 0

        # Workflow ended without reaching End node (shouldn't happen)
        logger.error("Merge failed - workflow ended unexpectedly")
        return 1
