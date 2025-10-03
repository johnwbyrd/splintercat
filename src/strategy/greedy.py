"""Greedy strategy - walk through patches, skip failures, test at end."""

from src.core.log import logger
from src.core.state import State
from src.patchset import PatchSet
from src.strategy.base import Strategy


class GreedyStrategy(Strategy):
    """Strategy that greedily walks through patches.

    Simple walk-through approach:
    1. Walk through all patches in order
    2. Skip patches that don't apply (mark as bad)
    3. Keep patches that do apply
    4. Test everything that applied
    5. If tests fail, bisect to find the bad one
    """

    def run(self, state: State, target) -> None:
        """Run greedy strategy to completion."""
        known_bad_apply = set(state.strategy_data.get("known_bad_apply", []))

        # Save checkpoint at start
        checkpoint = target.save_state()
        applied_patches = []

        # Walk through patches, skip bad ones
        logger.info("Walking through patches...")
        for patch in state.original_patchset:
            if patch.id in known_bad_apply:
                logger.debug(f"Skipping known bad patch {patch.id[:8]}")
                continue

            result = target.apply_one(patch)
            if not result.success:
                # Doesn't apply, mark it bad, keep walking
                known_bad_apply.add(result.failed_patch_id)
                state.strategy_data["known_bad_apply"] = list(known_bad_apply)
                logger.warning(f"Marked {result.failed_patch_id[:8]} as bad, continuing")
                continue

            applied_patches.append(patch)

        # Test what we got
        if not applied_patches:
            logger.info(
                f"Done! No patches applied. Skipped {len(known_bad_apply)} non-applying patches"
            )
            state.done = True
            return

        logger.info(f"Applied {len(applied_patches)} patches, testing...")
        if target.run_tests():
            # Success!
            logger.success(f"All {len(applied_patches)} patches passed tests!")
            state.record_result(
                PatchSet(applied_patches),
                success=True,
                applied=True,
                failed_patch_id=None
            )
            state.done = True
        else:
            # Tests failed - rollback and bisect
            logger.warning("Tests failed, rolling back to bisect")
            target.rollback(checkpoint)

            # TODO: Implement bisection to find which patch broke tests
            # For now, just mark as done
            logger.error("Bisection not yet implemented")
            state.record_result(
                PatchSet(applied_patches),
                success=False,
                applied=True,
                failed_patch_id=None
            )
            state.done = True
