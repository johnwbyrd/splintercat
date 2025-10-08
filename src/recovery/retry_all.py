"""Retry-all recovery: re-resolve all conflicts with failure context."""

from src.core.log import logger


class RetryAllRecovery:
    """Retry-all recovery strategy.

    Re-resolves all conflicts with failure context added to prompts.
    Used when failure suggests systemic misunderstanding.
    """

    @property
    def name(self) -> str:
        """Recovery strategy name."""
        return "retry_all"

    def execute(self, state: dict) -> dict:
        """Execute retry-all recovery.

        Clears all resolutions and adds failure context for re-resolution.

        Args:
            state: Current workflow state

        Returns:
            Updated state with resolutions cleared and failure context added
        """
        logger.info("Recovery: retry-all - re-resolving all conflicts with failure context")

        # Add failure context for resolver to use
        failure_summary = state.get("failure_summary")
        state["failure_context"] = {
            "error_type": failure_summary.error_type,
            "root_cause": failure_summary.root_cause,
            "location": failure_summary.location,
        }

        # Clear resolutions to force re-resolution
        state["resolutions"] = []
        state["conflicts_remaining"] = True

        return state
