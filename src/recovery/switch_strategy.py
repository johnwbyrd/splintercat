"""Switch-strategy recovery: change to more conservative approach."""

from src.core.log import logger


class SwitchStrategyRecovery:
    """Switch-strategy recovery.

    Changes to a more conservative strategy
    (optimistic → batch → per_conflict). Restarts merge with
    better isolation.
    """

    def __init__(self, new_strategy: str, batch_size: int | None = None):
        """Initialize switch-strategy recovery.

        Args:
            new_strategy: New strategy name (batch, per_conflict)
            batch_size: Batch size if new strategy is batch
        """
        self.new_strategy = new_strategy
        self.batch_size = batch_size

    @property
    def name(self) -> str:
        """Recovery strategy name."""
        return "switch_strategy"

    def execute(self, state: dict) -> dict:
        """Execute switch-strategy recovery.

        Resets to beginning with new strategy.

        Args:
            state: Current workflow state

        Returns:
            Updated state with new strategy
        """
        logger.info(
            f"Recovery: switch-strategy - changing to "
            f"{self.new_strategy}"
        )

        # Reset to clean state
        state["resolutions"] = []
        state["conflicts_remaining"] = True
        state["current_strategy"] = self.new_strategy

        if self.batch_size is not None:
            state["batch_size"] = self.batch_size

        # Will restart resolution loop with new strategy
        return state
