"""Retry-specific recovery: re-resolve only identified conflicts."""

from src.core.log import logger


class RetrySpecificRecovery:
    """Retry-specific recovery strategy.

    Re-resolves only the conflicts identified as problematic.
    Fastest recovery if analysis is correct.
    """

    def __init__(self, conflicts_to_retry: list[tuple[int, int]]):
        """Initialize retry-specific recovery.

        Args:
            conflicts_to_retry: List of (i1, i2) conflict pairs to retry
        """
        self.conflicts_to_retry = conflicts_to_retry

    @property
    def name(self) -> str:
        """Recovery strategy name."""
        return "retry_specific"

    def execute(self, state: dict) -> dict:
        """Execute retry-specific recovery.

        Keeps resolutions that aren't being retried, clears specific ones.

        Args:
            state: Current workflow state

        Returns:
            Updated state with specific resolutions cleared
        """
        logger.info(f"Recovery: retry-specific - re-resolving {len(self.conflicts_to_retry)} conflicts")

        # Filter resolutions to keep only those not being retried
        resolutions = state.get("resolutions", [])
        kept_resolutions = [
            r for r in resolutions
            if (r.i1, r.i2) not in self.conflicts_to_retry
        ]

        # Add failure context
        failure_summary = state.get("failure_summary")
        state["failure_context"] = {
            "error_type": failure_summary.error_type,
            "root_cause": failure_summary.root_cause,
            "location": failure_summary.location,
            "retrying_conflicts": self.conflicts_to_retry,
        }

        state["resolutions"] = kept_resolutions
        state["conflicts_remaining"] = True

        return state
