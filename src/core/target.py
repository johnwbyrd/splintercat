"""Target ABC and GitTarget implementation for applying and testing patches."""

from abc import ABC, abstractmethod

from src.core.command_runner import CommandRunner
from src.core.config import TargetConfig
from src.core.log import logger
from src.patchset import PatchSet


class Target(ABC):
    """Abstract base class for patch targets."""

    @abstractmethod
    def checkout(self):
        """Prepare target branch (create if needed, checkout if exists)."""

    @abstractmethod
    def try_patches(self, patchset: PatchSet) -> tuple[bool, bool]:
        """Apply patches, test, and rollback on failure (atomic operation).

        Args:
            patchset: PatchSet to apply

        Returns:
            (success, applied):
                - success: True if all patches applied and tests passed
                - applied: True if patches applied (even if tests failed)
        """

    @abstractmethod
    def commit(self, message: str):
        """Commit the currently applied patches.

        Args:
            message: Commit message
        """


class GitTarget(Target):
    """Applies patches to a git repository and tests them using git am."""

    def __init__(self, config: TargetConfig, test_cmd: str, runner: CommandRunner):
        """Initialize GitTarget.

        Args:
            config: Target configuration with branch, workdir, and commands
            test_cmd: Command to run for testing
            runner: CommandRunner instance for executing git commands
        """
        self.config = config
        self.test_cmd = test_cmd
        self.runner = runner

    def checkout(self):
        """Prepare target branch (create or reset based on force_recreate)."""
        branch_create_flag = "B" if self.config.force_recreate else "b"
        mode = "Creating/resetting" if self.config.force_recreate else "Creating"

        logger.info(f"{mode} target branch: {self.config.branch} from {self.config.base_ref}")
        self.runner.run(
            self.config.commands.checkout.format(
                branch_create_flag=branch_create_flag, **self.config.model_dump()
            )
        )
        logger.success(f"Branch {self.config.branch} ready")

    def try_patches(self, patchset: PatchSet) -> tuple[bool, bool]:
        """Apply patches, test, and rollback on failure (atomic operation).

        This is atomic from the Strategy's perspective - either everything
        succeeds (patches applied and tests pass) or everything is rolled back.

        Args:
            patchset: PatchSet to apply

        Returns:
            (success, applied):
                - success: True if all patches applied and tests passed
                - applied: True if patches applied (even if tests failed)
        """
        # Save current state for rollback
        state = self._get_current_state()
        logger.debug(f"Saved state: {state}")

        # Apply all patches
        if not self._apply_patches(patchset):
            logger.warning("Patches failed to apply - skipping tests, rolling back")
            self._rollback(state)
            return (False, False)

        # Run tests
        if not self._test():
            logger.warning("Tests failed, rolling back")
            self._rollback(state)
            return (False, True)

        logger.success(f"Successfully applied and tested {patchset.size()} patch(es)")
        return (True, True)

    def commit(self, message: str):
        """Commit the currently applied patches.

        Note: With git am, patches are already committed with proper attribution.
        This method is for compatibility with the Strategy interface.

        Args:
            message: Commit message (unused with git am)
        """
        logger.debug("Patches already committed via git am")

    def _get_current_state(self) -> str:
        """Get current git HEAD for rollback purposes.

        Returns:
            Current commit hash
        """
        result = self.runner.run(
            self.config.commands.get_state.format(**self.config.model_dump())
        )
        return result.stdout.strip()

    def _apply_patches(self, patchset: PatchSet) -> bool:
        """Apply patches using git am.

        git am preserves authorship and commit messages from the patch.

        Args:
            patchset: PatchSet to apply

        Returns:
            True if all patches applied successfully, False otherwise
        """
        for patch in patchset:
            logger.info(f"Applying patch {patch.id[:8]}: {patch.subject[:60]}")

            cmd = self.config.commands.apply.format(**self.config.model_dump())
            result = self.runner.run(cmd, stdin=patch.diff, check=False)

            if result.returncode != 0:
                logger.error(
                    f"Patch {patch.id[:8]} failed to apply (exit code {result.returncode})"
                )
                # Clean up git am state
                self.runner.run(
                    self.config.commands.apply_abort.format(**self.config.model_dump()), check=False
                )
                return False

            logger.success(f"Applied patch {patch.id[:8]}")

        return True

    def _test(self) -> bool:
        """Run the test command.

        Returns:
            True if tests passed (exit code 0), False otherwise
        """
        logger.info("Running tests...")
        result = self.runner.run(
            self.test_cmd.format(**self.config.model_dump()), check=False
        )

        if result.returncode == 0:
            logger.success("Tests passed")
            return True
        else:
            logger.error(f"Tests failed (exit code {result.returncode})")
            return False

    def _rollback(self, state: str):
        """Rollback to a previous state.

        Uses git reset --hard and git clean -fd to remove all changes
        including untracked files.

        Args:
            state: Git commit hash to roll back to
        """
        logger.info(f"Rolling back to {state[:8]}")

        # Clean up any git am state first (may exist from failed apply or test)
        self.runner.run(
            self.config.commands.apply_abort.format(**self.config.model_dump()), check=False
        )

        # Run reset and clean separately to avoid index.lock race conditions
        self.runner.run(
            self.config.commands.rollback_reset.format(state=state, **self.config.model_dump())
        )
        self.runner.run(self.config.commands.rollback_clean.format(**self.config.model_dump()))

        logger.warning("Rolled back changes")
