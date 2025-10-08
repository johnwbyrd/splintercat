"""Batch strategy: resolve N conflicts, test, repeat."""


class BatchStrategy:
    """Batch strategy - resolve N conflicts, then build/test.

    Balanced approach.
    Reasonable isolation with fewer builds than per-conflict.
    """

    def __init__(self, batch_size: int):
        """Initialize batch strategy.

        Args:
            batch_size: Number of conflicts to resolve before building
        """
        self.batch_size = batch_size

    @property
    def name(self) -> str:
        """Strategy name."""
        return "batch"

    def should_build_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Build after N conflicts resolved.

        Args:
            conflicts_resolved_this_batch: Number of conflicts resolved since last build

        Returns:
            True if batch size reached, False otherwise
        """
        return conflicts_resolved_this_batch >= self.batch_size

    def reset_batch(self) -> None:
        """Reset for next batch (no state to reset)."""
        pass
