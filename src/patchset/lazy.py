"""LazyPatchSet - generated patches on demand."""

from src.patchset.base import PatchSet


class LazyPatchSet(PatchSet):
    """PatchSet with patches generated on demand.

    Optimal for LLM rewrites and expensive transformations.
    """

    def __init__(self, generator):
        """Initialize LazyPatchSet.

        Args:
            generator: Callable that returns list of Patch objects
        """
        self.generator = generator
        self._cache = None

    def size(self) -> int:
        """Return the number of patches (triggers generation)."""
        raise NotImplementedError

    def get(self, index: int):
        """Retrieve a single patch by index."""
        raise NotImplementedError

    def __iter__(self):
        """Iterate over patches."""
        raise NotImplementedError

    def to_list(self) -> list:
        """Convert to list of Patch objects."""
        raise NotImplementedError

    def slice(self, start: int, end: int):
        """Extract a sub-range."""
        raise NotImplementedError

    def filter(self, predicate):
        """Filter patches."""
        raise NotImplementedError

    def union(self, other):
        """Combine with another PatchSet."""
        raise NotImplementedError

    def annotate(self, key: str, value_fn):
        """Attach metadata to patches."""
        raise NotImplementedError

    def metadata(self, index: int, key: str):
        """Retrieve metadata for a patch."""
        raise NotImplementedError
