"""Main application orchestrator for Splintercat."""

from src.core.config import Settings
from src.core.log import logger
from src.state.workflow import MergeWorkflowState
from src.workflow.graph import create_workflow


class SplintercatApp:
    """Main application that orchestrates the merge workflow."""

    def __init__(self, settings: Settings):
        """Initialize the application.

        Args:
            settings: Application configuration
        """
        self.settings = settings
        logger.setup(settings.verbose)

    async def run(self) -> int:
        """Run the merge workflow asynchronously.

        Returns:
            Exit code: 0 for success, 1 for failure
        """
        logger.info(
            f"Starting merge of {self.settings.source.ref} "
            f"into {self.settings.target.branch}"
        )

        # Create workflow
        workflow = create_workflow(self.settings)
        initial_state = MergeWorkflowState(**self._create_initial_state())

        from src.workflow.nodes.initialize import Initialize

        # Execute workflow with pydantic-graph API
        async with workflow.iter(Initialize(), state=initial_state) as run:
            end_result = None
            async for node in run:
                if hasattr(node, 'data'):  # End node
                    end_result = node.data
                    break

        # Report results
        if isinstance(end_result, str):  # Successfully reached End node with commit SHA
            logger.info(f"Merge complete! Final commit: {end_result}")
            return 0
        else:
            logger.error("Merge failed")
            return 1

    def _create_initial_state(self) -> dict:
        """Create initial workflow state from settings.

        Returns:
            Initial state dictionary
        """
        return {
            "imerge_name": self.settings.imerge.name,
            "workdir": self.settings.target.workdir,
            "source_ref": self.settings.source.ref,
            "target_branch": self.settings.target.branch,
            "current_strategy": "",
            "conflicts_in_batch": [],
            "attempts": [],
            "resolutions": [],
            "status": "initialized",
        }
