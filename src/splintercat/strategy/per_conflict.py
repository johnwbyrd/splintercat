"""Per-conflict strategy: resolve one conflict, check, repeat."""


class PerConflictStrategy:
    """Per-conflict strategy - resolve one conflict, then check
    immediately.

    Best isolation of failures.
    Slowest (most checks).
    Safest approach.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "per_conflict"

    def should_check_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Check after every conflict.

        Args:
            conflicts_resolved_this_batch: Number of conflicts
                resolved since last check

        Returns:
            True if any conflict resolved, False otherwise
        """
        return conflicts_resolved_this_batch >= 1

    def reset_batch(self) -> None:
        """Reset for next conflict (no state to reset)."""
        pass
