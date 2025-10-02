"""Source ABC and GitSource implementation for fetching patches."""

from abc import ABC, abstractmethod


class Source(ABC):
    """Abstract base class for patch sources."""

    @abstractmethod
    def get_patches(self) -> list:
        """Fetch patches from the source.

        Returns:
            List of Patch objects
        """
        raise NotImplementedError


class GitSource(Source):
    """Fetches patches from a git repository."""

    def __init__(self, config: dict, runner):
        """Initialize GitSource.

        Args:
            config: Source configuration from YAML
            runner: CommandRunner instance
        """
        self.config = config
        self.runner = runner

    def get_patches(self) -> list:
        """Fetch patches from git repository.

        Returns:
            List of Patch objects
        """
        raise NotImplementedError
