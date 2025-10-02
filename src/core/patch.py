"""Patch value object with lazy-computed properties."""

from dataclasses import dataclass, field


@dataclass
class Patch:
    """Represents a single patch with metadata.

    Attributes:
        id: Git commit hash or unique identifier
        diff: Full patch text
        metadata: Extensible metadata storage
    """

    id: str
    diff: str
    metadata: dict = field(default_factory=dict)

    @property
    def author(self) -> str:
        """Parse and return patch author (cached)."""
        raise NotImplementedError

    @property
    def changed_files(self) -> list[str]:
        """Parse and return list of changed files (cached)."""
        raise NotImplementedError

    @property
    def timestamp(self) -> str:
        """Parse and return patch timestamp (cached)."""
        raise NotImplementedError
