"""Bisect strategy - divide and conquer for faster application."""

from src.core.log import logger
from src.core.state import State
from src.patchset import PatchSet
from src.strategy.base import Strategy


class BisectStrategy(Strategy):
    """Strategy that uses bisection to find working patch subsets.

    Tries to apply as many patches as possible by bisecting around failures.
    Patches that fail when tested alone are marked as bad and skipped.
    """

    def next_attempt(self, state: State) -> PatchSet | None:
        """Decide what to try next using bisection.

        Algorithm:
        1. First attempt: try all patches optimistically
        2. On success: update frontier, try next unexplored range
        3. On failure (size 1): mark patch as bad, skip it, continue
        4. On failure (size > 1): bisect the range (try first half)

        Args:
            state: Complete state with original patches and all attempt history

        Returns:
            PatchSet to try next, or None if done
        """
        # Load strategy data
        strategy_data = state.strategy_data
        known_bad_ids = set(strategy_data.get("known_bad_ids", []))
        applied_up_to = strategy_data.get("applied_up_to_index", 0)
        current_bisect = strategy_data.get("current_bisect")

        total_patches = state.original_patchset.size()

        # First attempt: try everything optimistically
        if len(state.results) == 0:
            logger.info("First attempt: trying all patches optimistically")
            return state.original_patchset

        # Analyze last result
        last_result = state.results[-1]

        if last_result.success:
            # Success! Update frontier
            # Find highest index in successful result
            max_index = 0
            for patch_id in last_result.patch_ids:
                for i in range(state.original_patchset.size()):
                    if state.original_patchset.get(i).id == patch_id:
                        max_index = max(max_index, i)
                        break

            applied_up_to = max_index + 1
            strategy_data["applied_up_to_index"] = applied_up_to
            strategy_data["current_bisect"] = None
            current_bisect = None

            logger.success(
                f"Applied patches up to index {applied_up_to} " f"({applied_up_to}/{total_patches})"
            )

        else:
            # Failure - check if we know which specific patch failed to apply
            if last_result.failed_patch_id:
                # Patch failed to apply - mark as bad immediately, no need to bisect
                bad_patch_id = last_result.failed_patch_id
                known_bad_ids.add(bad_patch_id)
                strategy_data["known_bad_ids"] = list(known_bad_ids)
                strategy_data["current_bisect"] = None
                current_bisect = None

                logger.warning(
                    f"Patch {bad_patch_id[:8]} failed to apply - marking as bad and retrying without it"
                )

            elif len(last_result.patch_ids) == 1:
                # Single patch failed tests (not apply) - mark as bad and skip
                bad_patch_id = last_result.patch_ids[0]
                known_bad_ids.add(bad_patch_id)
                strategy_data["known_bad_ids"] = list(known_bad_ids)

                # Move frontier past this bad patch
                for i in range(applied_up_to, state.original_patchset.size()):
                    if state.original_patchset.get(i).id == bad_patch_id:
                        applied_up_to = i + 1
                        strategy_data["applied_up_to_index"] = applied_up_to
                        break

                strategy_data["current_bisect"] = None
                current_bisect = None

                logger.warning(
                    f"Patch {bad_patch_id[:8]} failed tests - marking as bad and skipping"
                )

            else:
                # Multiple patches, tests failed - need to bisect
                # Find the range indices
                start_index = applied_up_to
                end_index = start_index + len(last_result.patch_ids)

                # Try first half
                mid_index = (start_index + end_index) // 2
                strategy_data["current_bisect"] = {
                    "start": start_index,
                    "end": end_index,
                    "mid": mid_index,
                }
                current_bisect = strategy_data["current_bisect"]

                logger.info(
                    f"Tests failed for range [{start_index}, {end_index}) - bisecting to first half"
                )

        # Decide what to try next
        # Skip known bad patches and already applied patches
        remaining_start = applied_up_to
        remaining_count = 0

        for i in range(remaining_start, total_patches):
            patch = state.original_patchset.get(i)
            if patch.id not in known_bad_ids:
                remaining_count += 1
            else:
                # Hit a bad patch - can't skip over it yet in this naive implementation
                # We need to move frontier past all contiguous bad patches
                remaining_start = i + 1

        # Check if done
        if remaining_start >= total_patches:
            logger.info(
                f"Done! Applied {applied_up_to} patches, skipped {len(known_bad_ids)} bad patches"
            )
            state.done = True
            return None

        # If we're bisecting, try the appropriate range
        if current_bisect:
            start = current_bisect["start"]
            mid = current_bisect["mid"]
            size = mid - start
            logger.debug(f"Trying bisected range [{start}, {mid}) - {size} patches")
            return state.original_patchset.slice(start, mid)

        # Otherwise, try all remaining patches
        end_index = total_patches
        # Find first known-bad patch in remaining range
        for i in range(remaining_start, total_patches):
            if state.original_patchset.get(i).id in known_bad_ids:
                end_index = i
                break

        size = end_index - remaining_start
        if size > 0:
            logger.debug(
                f"Trying remaining range [{remaining_start}, {end_index}) - {size} patches"
            )
            return state.original_patchset.slice(remaining_start, end_index)
        else:
            logger.info("No more patches to try")
            state.done = True
            return None
