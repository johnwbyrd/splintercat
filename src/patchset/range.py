"""RangePatchSet - contiguous ranges with O(1) operations."""

from src.patchset.base import PatchSet


class RangePatchSet(PatchSet):
    """PatchSet representing a contiguous range of patches.

    Optimal for bisection and sequential processing.
    """

    def __init__(self, source: list, start: int, end: int):
        """Initialize RangePatchSet.

        Args:
            source: List of all Patch objects
            start: Start index (inclusive)
            end: End index (exclusive)
        """
        self.source = source
        self.start = start
        self.end = end

    def size(self) -> int:
        """Return the number of patches in this range."""
        raise NotImplementedError

    def get(self, index: int):
        """Retrieve a single patch by index."""
        raise NotImplementedError

    def __iter__(self):
        """Iterate over patches in this range."""
        raise NotImplementedError

    def to_list(self) -> list:
        """Convert to list of Patch objects."""
        raise NotImplementedError

    def slice(self, start: int, end: int):
        """Extract a sub-range (O(1) operation)."""
        raise NotImplementedError

    def filter(self, predicate):
        """Filter patches (returns IndexedPatchSet)."""
        raise NotImplementedError

    def union(self, other):
        """Combine with another PatchSet (returns ComposedPatchSet)."""
        raise NotImplementedError

    def annotate(self, key: str, value_fn):
        """Attach metadata to patches."""
        raise NotImplementedError

    def metadata(self, index: int, key: str):
        """Retrieve metadata for a patch."""
        raise NotImplementedError
