"""Base recovery interface."""

from abc import abstractmethod
from typing import Protocol


class Recovery(Protocol):
    """Protocol for recovery strategies.

    A recovery strategy determines how to respond to build/test failures.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Recovery strategy name."""
        pass

    @abstractmethod
    def execute(self, state: dict) -> dict:
        """Execute recovery strategy.

        Args:
            state: Current workflow state including failure information

        Returns:
            Updated state with recovery actions applied
        """
        pass
