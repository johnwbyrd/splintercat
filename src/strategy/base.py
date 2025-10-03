"""Strategy ABC for patch application decision-making."""

from abc import ABC, abstractmethod

from src.core.state import State


class Strategy(ABC):
    """Abstract base class for patch application strategies.

    Strategy drives the target to apply and test patches.
    """

    @abstractmethod
    def run(self, state: State, target) -> None:
        """Run strategy to completion.

        Strategy has full control over target operations.
        Updates state with results.
        Sets state.done = True when finished.

        Args:
            state: Complete state with original patches and results
            target: Target to apply patches to
        """
