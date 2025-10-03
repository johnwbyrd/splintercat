"""SequentialStrategy - try patches one at a time in order."""

from src.core.log import logger
from src.core.state import State
from src.patchset import PatchSet
from src.strategy.base import Strategy


class SequentialStrategy(Strategy):
    """Try all patches first (optimistic), then one at a time on failure."""

    def next_attempt(self, state: State) -> PatchSet | None:
        """Decide what to try next.

        Strategy:
        1. First attempt: try ALL patches (optimistic - best case is one build)
        2. If that works: done!
        3. Otherwise: try patches one at a time
        4. Give up when all individual patches have been tried

        Args:
            state: Current state with attempt history

        Returns:
            PatchSet to try next, or None if done
        """
        # First attempt: try everything!
        if len(state.results) == 0:
            logger.info("First attempt: trying all patches optimistically")
            return state.original_patchset

        # If the first "try all" succeeded, we're done!
        if state.results[0].success:
            logger.success("All patches succeeded on first attempt!")
            state.done = True
            return None

        # Otherwise, try one patch at a time
        # -1 because first attempt was "all patches"
        attempted_count = len(state.results) - 1

        if attempted_count >= state.original_patchset.size():
            logger.info("All individual patches attempted")
            state.done = True
            return None

        # Try next single patch
        logger.debug(f"Trying individual patch {attempted_count + 1}")
        return state.original_patchset.slice(attempted_count, attempted_count + 1)
