"""Bisect recovery: binary search for problematic resolution."""

from src.core.log import logger


class BisectRecovery:
    """Bisect recovery strategy.

    Uses binary search to narrow down problematic resolution(s).
    O(log N) builds to isolate issue.
    """

    @property
    def name(self) -> str:
        """Recovery strategy name."""
        return "bisect"

    def execute(self, state: dict) -> dict:
        """Execute bisect recovery.

        Simplified bisect: split resolutions in half, test each half.

        Args:
            state: Current workflow state

        Returns:
            Updated state configured for bisect testing
        """
        logger.info("Recovery: bisect - searching for problematic resolution")

        resolutions = state.get("resolutions", [])
        mid = len(resolutions) // 2

        # Start by testing first half
        state["bisect_mode"] = True
        state["bisect_range"] = (0, mid)
        state["bisect_full_resolutions"] = resolutions
        state["resolutions"] = resolutions[:mid]

        logger.debug(f"Bisect: testing first half ({mid} resolutions)")

        return state
