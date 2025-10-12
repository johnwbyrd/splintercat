"""Optimistic strategy: resolve all conflicts, then check once."""


class OptimisticStrategy:
    """Optimistic strategy - resolve all conflicts before first check.

    Fastest if successful (only 1 check).
    Hard to isolate failures.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "optimistic"

    def should_check_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Never check until all conflicts resolved.

        Args:
            conflicts_resolved_this_batch: Number of conflicts
                resolved (ignored)

        Returns:
            Always False - never check during conflict
                resolution
        """
        return False

    def reset_batch(self) -> None:
        """No-op for optimistic strategy."""
        pass
