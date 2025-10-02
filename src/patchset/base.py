"""Abstract base class for PatchSet implementations."""

from abc import ABC, abstractmethod


class PatchSet(ABC):
    """Abstract base class for patch collections."""

    @abstractmethod
    def size(self) -> int:
        """Return the number of patches in this set."""
        raise NotImplementedError

    @abstractmethod
    def get(self, index: int):
        """Retrieve a single patch by index.

        Args:
            index: Zero-based index

        Returns:
            Patch object
        """
        raise NotImplementedError

    @abstractmethod
    def __iter__(self):
        """Iterate over patches in this set."""
        raise NotImplementedError

    @abstractmethod
    def to_list(self) -> list:
        """Convert to list of Patch objects.

        Returns:
            List of Patch objects
        """
        raise NotImplementedError

    @abstractmethod
    def slice(self, start: int, end: int):
        """Extract a contiguous range.

        Args:
            start: Start index (inclusive)
            end: End index (exclusive)

        Returns:
            New PatchSet containing the range
        """
        raise NotImplementedError

    @abstractmethod
    def filter(self, predicate):
        """Select patches matching a condition.

        Args:
            predicate: Function that takes a Patch and returns bool

        Returns:
            New PatchSet containing matching patches
        """
        raise NotImplementedError

    @abstractmethod
    def union(self, other):
        """Combine with another PatchSet.

        Args:
            other: Another PatchSet

        Returns:
            New PatchSet containing patches from both sets
        """
        raise NotImplementedError

    @abstractmethod
    def annotate(self, key: str, value_fn):
        """Attach metadata to patches.

        Args:
            key: Metadata key
            value_fn: Function that takes a Patch and returns a value

        Returns:
            New PatchSet with metadata attached
        """
        raise NotImplementedError

    @abstractmethod
    def metadata(self, index: int, key: str):
        """Retrieve metadata for a patch.

        Args:
            index: Patch index
            key: Metadata key

        Returns:
            Metadata value
        """
        raise NotImplementedError
