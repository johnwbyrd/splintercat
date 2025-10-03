"""Runner - main application logic for patch application."""

from src.core.command_runner import CommandRunner
from src.core.config import Settings
from src.core.log import logger, setup_logging
from src.core.source import GitSource
from src.core.state import State
from src.core.target import GitTarget
from src.strategy import BisectStrategy


class Runner:
    """Orchestrates the patch application workflow."""

    def __init__(self, settings: Settings):
        """Initialize Runner with settings.

        Args:
            settings: Application settings from config
        """
        self.settings = settings

    def run(self):
        """Execute the patch application workflow.

        Workflow:
        1. Setup logging
        2. Create components (runner, source, target, strategy)
        3. Get patches from source
        4. Initialize state
        5. Prepare target branch
        6. Main loop: strategy decides, target tries, record results
        7. Report final results
        """
        # Setup
        setup_logging(self.settings.verbose)
        logger.info("Starting splintercat")

        # Create components
        runner = CommandRunner(self.settings.interactive)
        source = GitSource(self.settings.source, runner, self.settings.log_truncate_length)
        target = GitTarget(self.settings.target, self.settings.test_command, runner)
        strategy = BisectStrategy()

        # Get all patches from source
        original_patches = source.get_patches()
        logger.info(f"Fetched {original_patches.size()} patches")

        if original_patches.size() == 0:
            logger.warning("No patches to process")
            return

        # Initialize state
        state = State(original_patchset=original_patches)

        # Prepare target branch
        target.checkout()

        # Main loop - run until strategy says done
        while not state.done:
            # Strategy decides what to try next
            next_set = strategy.next_attempt(state)

            if next_set is None:
                break

            # Target tries the patches (atomic operation)
            logger.info(f"Attempting {next_set.size()} patch(es)...")
            success = target.try_patches(next_set)

            # Record result for strategy to analyze
            state.record_result(next_set, success)

        # Report final results
        self._report_results(state)

    def _report_results(self, state: State):
        """Report final results.

        Args:
            state: Final state with all results
        """
        total_attempts = len(state.results)
        successes = sum(1 for r in state.results if r.success)
        failures = total_attempts - successes

        logger.info(f"Complete! {total_attempts} total attempts")
        logger.success(f"Successes: {successes}")

        if failures > 0:
            logger.warning(f"Failures: {failures}")

        # Log which patches succeeded (if not the first "all" attempt)
        if total_attempts > 1:
            successful_patches = []
            for result in state.results[1:]:
                if result.success and len(result.patch_ids) == 1:
                    successful_patches.extend(result.patch_ids)

            if successful_patches:
                logger.info(f"Successfully applied {len(successful_patches)} individual patches")
