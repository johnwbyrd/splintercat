"""Target ABC and GitTarget implementation for applying and testing patches."""

from abc import ABC, abstractmethod

from src.core.command_runner import CommandRunner
from src.core.config import TargetConfig
from src.core.log import logger
from src.core.patch import Patch
from src.core.result import ApplyResult


class Target(ABC):
    """Abstract base class for patch targets."""

    @abstractmethod
    def checkout(self):
        """Prepare target branch (create if needed, checkout if exists)."""

    @abstractmethod
    def save_state(self) -> str:
        """Capture current state for rollback.

        Returns:
            Opaque state identifier (e.g., git commit hash)
        """

    @abstractmethod
    def apply_one(self, patch: Patch) -> ApplyResult:
        """Apply a single patch.

        Returns:
            ApplyResult with success status and failed_patch_id if applicable
        """

    @abstractmethod
    def run_tests(self) -> bool:
        """Execute test suite.

        Returns:
            True if tests passed
        """

    @abstractmethod
    def rollback(self, state: str):
        """Restore to previous state.

        Rollback aggressiveness determined by target configuration.

        Args:
            state: State identifier from save_state()
        """

    @abstractmethod
    def commit(self, message: str):
        """Commit the currently applied patches.

        Args:
            message: Commit message
        """


class GitTarget(Target):
    """Applies patches to a git repository and tests them using git cherry-pick."""

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
        # Check if working directory is clean
        result = self.runner.run(
            self.config.commands.check_clean.format(**self.config.model_dump()), check=False
        )
        if result.returncode != 0:
            logger.error("Working directory is dirty - cannot apply patches")
            logger.error("Please commit or stash your changes before running splintercat")
            raise RuntimeError("Dirty working directory")

        branch_create_flag = "B" if self.config.force_recreate else "b"
        mode = "Creating/resetting" if self.config.force_recreate else "Creating"

        logger.info(f"{mode} target branch: {self.config.branch} from {self.config.base_ref}")
        self.runner.run(
            self.config.commands.checkout.format(
                branch_create_flag=branch_create_flag, **self.config.model_dump()
            )
        )
        logger.success(f"Branch {self.config.branch} ready")

    def save_state(self) -> str:
        """Get current git HEAD for rollback."""
        result = self.runner.run(
            self.config.commands.get_state.format(**self.config.model_dump())
        )
        return result.stdout.strip()

    def apply_one(self, patch: Patch) -> ApplyResult:
        """Apply a single patch using git cherry-pick."""
        logger.info(f"Cherry-picking {patch.id[:8]}: {patch.subject[:60]}")

        cmd = self.config.commands.apply.format(commit=patch.id, **self.config.model_dump())
        result = self.runner.run(cmd, check=False)

        if result.returncode != 0:
            logger.error(
                f"Cherry-pick {patch.id[:8]} failed (exit code {result.returncode})"
            )
            # Clean up cherry-pick state
            self.runner.run(
                self.config.commands.apply_abort.format(**self.config.model_dump()),
                check=False
            )
            return ApplyResult(success=False, failed_patch_id=patch.id)

        logger.success(f"Cherry-picked {patch.id[:8]}")
        return ApplyResult(success=True, failed_patch_id=None)

    def run_tests(self) -> bool:
        """Run the test command."""
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

    def rollback(self, state: str):
        """Rollback to previous git state.

        Always resets source code. Optionally cleans untracked files
        based on preserve_build_artifacts config.
        """
        logger.info(f"Rolling back to {state[:8]}")

        # Clean up any cherry-pick state first
        self.runner.run(
            self.config.commands.apply_abort.format(**self.config.model_dump()),
            check=False
        )

        # Always reset source code
        self.runner.run(
            self.config.commands.rollback_reset.format(state=state, **self.config.model_dump())
        )

        # Conditionally clean untracked files (build artifacts)
        if not self.config.preserve_build_artifacts:
            self.runner.run(
                self.config.commands.rollback_clean.format(**self.config.model_dump())
            )

        logger.warning("Rolled back changes")

    def commit(self, message: str):
        """Commit the currently applied patches.

        Note: With git cherry-pick, patches are already committed with proper attribution.
        This method is for compatibility with the Strategy interface.

        Args:
            message: Commit message (unused with git cherry-pick)
        """
        logger.debug("Patches already committed via git cherry-pick")
