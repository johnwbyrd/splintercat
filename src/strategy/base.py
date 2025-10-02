"""Abstract base class for Strategy implementations."""

from abc import ABC, abstractmethod


class Strategy(ABC):
    """Abstract base class for patch application strategies."""

    @abstractmethod
    def apply(self, patchset, target):
        """Apply patches from patchset to target.

        Args:
            patchset: PatchSet to apply
            target: GitTarget to apply to

        Returns:
            Result object describing what was applied
        """
        raise NotImplementedError
