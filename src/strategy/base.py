"""Strategy ABC for patch application decision-making."""

from abc import ABC, abstractmethod

from src.core.state import State
from src.patchset import PatchSet


class Strategy(ABC):
    """Abstract base class for patch application strategies.

    Strategy is a pure function that analyzes State and decides what to try next.
    """

    @abstractmethod
    def next_attempt(self, state: State) -> PatchSet | None:
        """Decide what to try next based on current state.

        Args:
            state: Complete state with original patches and all attempt history

        Returns:
            PatchSet to try next, or None (strategy should set state.done=True)
        """
