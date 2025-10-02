"""ComposedPatchSet - union of multiple PatchSets."""

from src.patchset.base import PatchSet


class ComposedPatchSet(PatchSet):
    """PatchSet representing a union of other PatchSets.

    Optimal for arbitrary reordering and look-ahead fixes.
    """

    def __init__(self, children: list[PatchSet]):
        """Initialize ComposedPatchSet.

        Args:
            children: List of PatchSet objects to compose
        """
        self.children = children

    def size(self) -> int:
        """Return the total number of patches across all children."""
        raise NotImplementedError

    def get(self, index: int):
        """Retrieve a single patch by index."""
        raise NotImplementedError

    def __iter__(self):
        """Iterate over all patches in all children."""
        raise NotImplementedError

    def to_list(self) -> list:
        """Convert to list of Patch objects."""
        raise NotImplementedError

    def slice(self, start: int, end: int):
        """Extract a sub-range."""
        raise NotImplementedError

    def filter(self, predicate):
        """Filter patches across all children."""
        raise NotImplementedError

    def union(self, other):
        """Combine with another PatchSet (add to children)."""
        raise NotImplementedError

    def annotate(self, key: str, value_fn):
        """Attach metadata to patches."""
        raise NotImplementedError

    def metadata(self, index: int, key: str):
        """Retrieve metadata for a patch."""
        raise NotImplementedError
