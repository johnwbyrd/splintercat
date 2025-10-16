"""Check node - run checks specified by planner."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger
from splintercat.runner.check import CheckRunner


@dataclass
class Check(BaseNode[State]):
    """Run checks specified by planner."""

    check_names: list[str]

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "ResolveConflicts | Finalize":
        """Run checks and route based on result.

        Returns:
            ResolveConflicts: If check fails (retry) or conflicts remain
            Finalize: If checks pass and no conflicts remain
        """
        runner = CheckRunner(
            ctx.state.config.git.target_workdir,
            ctx.state.config.check.output_dir
        )

        for name in self.check_names:
            cmd = ctx.state.config.check.commands.get(name)
            if not cmd:
                logger.error(f"Check '{name}' not defined in config")
                continue

            logger.info(f"Running check: {name}")
            result = runner.run(
                name,
                cmd,
                ctx.state.config.check.timeout
            )

            if not result.success:
                # Check failed
                ctx.state.runtime.merge.last_failed_check = result
                ctx.state.runtime.merge.retry_count += 1

                # Check if max retries exceeded
                max_retries = ctx.state.config.strategy.max_retries
                if ctx.state.runtime.merge.retry_count > max_retries:
                    logger.error(
                        f"Max retries ({max_retries}) exceeded. Aborting."
                    )
                    raise RuntimeError(
                        f"Check '{name}' failed after {max_retries} "
                        f"retry attempts"
                    )

                # If no conflicts remain, can't retry by re-resolving
                if not ctx.state.runtime.merge.conflicts_remaining:
                    logger.error(
                        f"Check '{name}' failed but all conflicts are "
                        f"resolved. Cannot retry - merge is complete but "
                        f"broken. See log: {result.log_file}"
                    )
                    raise RuntimeError(
                        f"Check '{name}' failed on completed merge. "
                        f"All conflicts were resolved but the final merge "
                        f"does not pass checks. Manual intervention required. "
                        f"Log: {result.log_file}"
                    )

                logger.warning(
                    f"Check '{name}' failed "
                    f"(attempt {ctx.state.runtime.merge.retry_count}"
                    f"/{max_retries}). Retrying batch with error context."
                )

                # Retry: go back to ResolveConflicts
                from splintercat.workflow.nodes.resolve_conflicts import (
                    ResolveConflicts,
                )
                return ResolveConflicts()

        # All checks passed - reset retry counter
        ctx.state.runtime.merge.retry_count = 0

        # Route based on whether conflicts remain
        if ctx.state.runtime.merge.conflicts_remaining:
            logger.info("All checks passed. Resolving next batch.")
            from splintercat.workflow.nodes.resolve_conflicts import (
                ResolveConflicts,
            )
            return ResolveConflicts()
        else:
            logger.info("All checks passed. No conflicts remain. Finalizing.")
            from splintercat.workflow.nodes.finalize import Finalize
            return Finalize()
