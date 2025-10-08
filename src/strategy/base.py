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
    def should_build_now(self, conflicts_resolved_this_batch: int) -> bool:
        """Determine if we should build/test now.

        Args:
            conflicts_resolved_this_batch: Number of conflicts resolved since last build

        Returns:
            True if should run build/test now, False to continue resolving
        """
        pass

    @abstractmethod
    def reset_batch(self) -> None:
        """Reset batch counter for next iteration."""
        pass
