"""PatchSet - lightweight wrapper around list[Patch] with efficient slicing."""

from src.core.patch import Patch


class PatchSet:
    """Ordered collection of patches with O(1) slicing.

    Wraps a list of patches with start/end indices for efficient sub-range operations.
    """

    def __init__(self, patches: list[Patch], start: int = 0, end: int | None = None):
        """Initialize PatchSet.

        Args:
            patches: List of Patch objects
            start: Start index (inclusive), defaults to 0
            end: End index (exclusive), defaults to len(patches)
        """
        self.patches = patches
        self.start = start
        self.end = end if end is not None else len(patches)

    def size(self) -> int:
        """Return the number of patches in this set."""
        return self.end - self.start

    def get(self, index: int) -> Patch:
        """Retrieve a single patch by index.

        Args:
            index: Zero-based index into this set

        Returns:
            Patch object

        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= self.size():
            raise IndexError(f"Index {index} out of range for size {self.size()}")
        return self.patches[self.start + index]

    def __iter__(self):
        """Iterate over patches in this set."""
        return iter(self.patches[self.start : self.end])

    def slice(self, start: int, end: int) -> "PatchSet":
        """Extract a sub-range (O(1) operation).

        Args:
            start: Start index relative to this set
            end: End index relative to this set

        Returns:
            New PatchSet containing the sub-range
        """
        return PatchSet(self.patches, self.start + start, self.start + end)
