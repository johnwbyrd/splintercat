"""Per-conflict strategy: resolve one conflict, test, repeat."""


class PerConflictStrategy:
    """Per-conflict strategy - resolve one conflict, then build/test immediately.

    Best isolation of failures.
    Slowest (most builds).
    Safest approach.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "per_conflict"

    def should_build_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Build after every conflict.

        Args:
            conflicts_resolved_this_batch: Number of conflicts resolved since last build

        Returns:
            True if any conflict resolved, False otherwise
        """
        return conflicts_resolved_this_batch >= 1

    def reset_batch(self) -> None:
        """Reset for next conflict (no state to reset)."""
        pass
