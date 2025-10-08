"""Main application orchestrator for Splintercat."""

from src.core.config import Settings
from src.core.log import logger, setup_logging
from src.workflow.graph import create_workflow


class SplintercatApp:
    """Main application that orchestrates the merge workflow."""

    def __init__(self, settings: Settings):
        """Initialize the application.

        Args:
            settings: Application configuration
        """
        self.settings = settings
        setup_logging(settings.verbose)

    def run(self) -> int:
        """Run the merge workflow.

        Returns:
            Exit code: 0 for success, 1 for failure
        """
        logger.info(f"Starting merge of {self.settings.source.ref} into {self.settings.target.branch}")

        # Create and run workflow
        workflow = create_workflow(self.settings)
        final_state = workflow.invoke(self._create_initial_state())

        # Report results
        if final_state.get("status") == "complete":
            logger.success(f"Merge complete! Final commit: {final_state['final_commit']}")
            return 0
        else:
            logger.error("Merge failed")
            if final_state.get("failure_summary"):
                logger.error(f"Last failure: {final_state['failure_summary'].root_cause}")
            return 1

    def _create_initial_state(self) -> dict:
        """Create initial workflow state from settings.

        Returns:
            Initial state dictionary
        """
        return {
            "settings": self.settings,
            "source_ref": self.settings.source.ref,
            "target_branch": self.settings.target.branch,
            "workdir": self.settings.target.workdir,
            "imerge_name": self.settings.imerge.name,
            "current_attempt": 0,
            "attempt_history": [],
            "conflicts_remaining": True,
            "resolutions": [],
            "status": "initialized",
        }
