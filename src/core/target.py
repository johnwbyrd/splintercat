"""GitTarget implementation for applying and testing patches."""


class GitTarget:
    """Applies patches to a git repository and tests them."""

    def __init__(self, config: dict, test_cmd: str, runner):
        """Initialize GitTarget.

        Args:
            config: Target configuration from YAML
            test_cmd: Command to run for testing
            runner: CommandRunner instance
        """
        self.config = config
        self.test_cmd = test_cmd
        self.runner = runner

    def checkout(self):
        """Prepare target branch (create if needed, checkout if exists)."""
        raise NotImplementedError

    def try_patches(self, patches: list) -> bool:
        """Apply patches, test, and rollback on failure (atomic operation).

        Args:
            patches: List of Patch objects to apply

        Returns:
            True if all patches applied and tests passed, False otherwise
        """
        raise NotImplementedError

    def commit(self, message: str):
        """Commit the currently applied patches.

        Args:
            message: Commit message
        """
        raise NotImplementedError
