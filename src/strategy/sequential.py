"""Sequential strategy - try patches one at a time in order."""

from src.strategy.base import Strategy


class SequentialStrategy(Strategy):
    """Strategy that tries patches one at a time in order."""

    def __init__(self, config: dict):
        """Initialize SequentialStrategy.

        Args:
            config: Strategy configuration from YAML
        """
        self.config = config

    def apply(self, patchset, target):
        """Try each patch sequentially.

        Args:
            patchset: PatchSet to apply
            target: GitTarget to apply to

        Returns:
            Result object describing what was applied
        """
        raise NotImplementedError
