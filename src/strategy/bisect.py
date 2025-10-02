"""Bisect strategy - divide and conquer for faster application."""

from src.strategy.base import Strategy


class BisectStrategy(Strategy):
    """Strategy that uses bisection to find working patch subsets."""

    def __init__(self, config: dict):
        """Initialize BisectStrategy.

        Args:
            config: Strategy configuration from YAML
        """
        self.config = config

    def apply(self, patchset, target):
        """Try whole set, bisect on failure.

        Args:
            patchset: PatchSet to apply
            target: GitTarget to apply to

        Returns:
            Result object describing what was applied
        """
        raise NotImplementedError
