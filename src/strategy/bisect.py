"""Bisect strategy - divide and conquer for faster application."""

from src.core.state import State
from src.patchset import PatchSet
from src.strategy.base import Strategy


class BisectStrategy(Strategy):
    """Strategy that uses bisection to find working patch subsets.

    Not yet implemented - placeholder for Phase 2.
    """

    def next_attempt(self, state: State) -> PatchSet | None:
        """Decide what to try next using bisection.

        Args:
            state: Complete state with original patches and all attempt history

        Returns:
            PatchSet to try next, or None if done
        """
        raise NotImplementedError("BisectStrategy not yet implemented")
