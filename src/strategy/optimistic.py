"""Optimistic strategy: resolve all conflicts, then test once."""


class OptimisticStrategy:
    """Optimistic strategy - resolve all conflicts before first build.

    Fastest if successful (only 1 build).
    Hard to isolate failures.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "optimistic"

    def should_build_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Never build until all conflicts resolved.

        Args:
            conflicts_resolved_this_batch: Number of conflicts resolved (ignored)

        Returns:
            Always False - never build during conflict resolution
        """
        return False

    def reset_batch(self) -> None:
        """No-op for optimistic strategy."""
        pass
