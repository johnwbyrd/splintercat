"""RangePatchSet - contiguous ranges with O(1) operations."""

from src.core.patch import Patch
from src.patchset.base import PatchSet


class RangePatchSet(PatchSet):
    """PatchSet representing a contiguous range of patches.

    Optimal for bisection and sequential processing with O(1) slicing.
    """

    def __init__(self, source: list[Patch], start: int = 0, end: int | None = None):
        """Initialize RangePatchSet.

        Args:
            source: List of all Patch objects
            start: Start index (inclusive), defaults to 0
            end: End index (exclusive), defaults to len(source)
        """
        self.source = source
        self.start = start
        self.end = end if end is not None else len(source)

    def size(self) -> int:
        """Return the number of patches in this range."""
        return self.end - self.start

    def get(self, index: int) -> Patch:
        """Retrieve a single patch by index.

        Args:
            index: Zero-based index into this range

        Returns:
            Patch object

        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= self.size():
            raise IndexError(f"Index {index} out of range for size {self.size()}")
        return self.source[self.start + index]

    def __iter__(self):
        """Iterate over patches in this range."""
        return iter(self.source[self.start : self.end])

    def to_list(self) -> list[Patch]:
        """Convert to list of Patch objects.

        Returns:
            List of Patch objects in this range
        """
        return list(self.source[self.start : self.end])

    def slice(self, start: int, end: int) -> "RangePatchSet":
        """Extract a sub-range (O(1) operation).

        Args:
            start: Start index relative to this range
            end: End index relative to this range

        Returns:
            New RangePatchSet containing the sub-range
        """
        return RangePatchSet(self.source, self.start + start, self.start + end)

    def filter(self, predicate):
        """Filter patches (returns IndexedPatchSet).

        Not implemented yet - use IndexedPatchSet directly for now.

        Args:
            predicate: Function that takes a Patch and returns bool

        Raises:
            NotImplementedError: Filter not yet implemented
        """
        raise NotImplementedError("Use IndexedPatchSet for filtering")

    def union(self, other):
        """Combine with another PatchSet (returns ComposedPatchSet).

        Not implemented yet - use ComposedPatchSet directly for now.

        Args:
            other: Another PatchSet

        Raises:
            NotImplementedError: Union not yet implemented
        """
        raise NotImplementedError("Use ComposedPatchSet for unions")

    def annotate(self, key: str, value_fn):
        """Attach metadata to patches.

        Args:
            key: Metadata key
            value_fn: Function that takes a Patch and returns a value

        Returns:
            Self (for chaining)
        """
        for patch in self:
            patch.metadata[key] = value_fn(patch)
        return self

    def metadata(self, index: int, key: str):
        """Retrieve metadata for a patch.

        Args:
            index: Patch index
            key: Metadata key

        Returns:
            Metadata value, or None if not found
        """
        patch = self.get(index)
        return patch.metadata.get(key)
