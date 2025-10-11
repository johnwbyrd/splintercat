"""Batch strategy: resolve N conflicts, check, repeat."""


class BatchStrategy:
    """Batch strategy - resolve N conflicts, then check.

    Balanced approach.
    Reasonable isolation with fewer checks than per-conflict.
    """

    def __init__(self, batch_size: int):
        """Initialize batch strategy.

        Args:
            batch_size: Number of conflicts to resolve before checking
        """
        self.batch_size = batch_size

    @property
    def name(self) -> str:
        """Strategy name."""
        return "batch"

    def should_check_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Check after N conflicts resolved.

        Args:
            conflicts_resolved_this_batch: Number of conflicts resolved since last check

        Returns:
            True if batch size reached, False otherwise
        """
        return conflicts_resolved_this_batch >= self.batch_size

    def reset_batch(self) -> None:
        """Reset for next batch (no state to reset)."""
        pass
