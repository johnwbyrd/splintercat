"""Base strategy interface."""

from abc import abstractmethod
from typing import Protocol


class Strategy(Protocol):
    """Protocol for merge strategies.

    A strategy determines how conflicts are batched for resolution and testing.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name (optimistic, batch, per_conflict)."""
        pass

    @abstractmethod
    def should_check_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Determine if we should run checks now.

        Args:
            conflicts_resolved_this_batch: Number of conflicts resolved since last check

        Returns:
            True if should run checks now, False to continue resolving
        """
        pass

    @abstractmethod
    def reset_batch(self) -> None:
        """Reset batch counter for next iteration."""
        pass
