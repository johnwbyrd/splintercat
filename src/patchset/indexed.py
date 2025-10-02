"""IndexedPatchSet - arbitrary subsets via index lists."""

from src.patchset.base import PatchSet


class IndexedPatchSet(PatchSet):
    """PatchSet representing an arbitrary subset of patches.

    Optimal for filtering and reordering.
    """

    def __init__(self, source: list, indices: list[int]):
        """Initialize IndexedPatchSet.

        Args:
            source: List of all Patch objects
            indices: List of indices into source
        """
        self.source = source
        self.indices = indices

    def size(self) -> int:
        """Return the number of patches in this set."""
        raise NotImplementedError

    def get(self, index: int):
        """Retrieve a single patch by index."""
        raise NotImplementedError

    def __iter__(self):
        """Iterate over patches in this set."""
        raise NotImplementedError

    def to_list(self) -> list:
        """Convert to list of Patch objects."""
        raise NotImplementedError

    def slice(self, start: int, end: int):
        """Extract a sub-range."""
        raise NotImplementedError

    def filter(self, predicate):
        """Filter patches (returns new IndexedPatchSet)."""
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
