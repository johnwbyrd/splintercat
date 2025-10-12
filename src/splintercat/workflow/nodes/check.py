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
    ) -> "SummarizeFailure | ResolveConflicts | Finalize":
        """Run checks and route on failure.

        Returns:
            SummarizeFailure: If any check fails
            ResolveConflicts: If conflicts remain after checks
                pass
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
                ctx.state.config.check.default_timeout
            )

            # Record result in state
            ctx.state.runtime.merge.check_results.append(result)

            if not result.success:
                ctx.state.runtime.merge.last_failed_check = result
                from splintercat.workflow.nodes.summarize_failure import (
                    SummarizeFailure,
                )

                return SummarizeFailure()

        # All checks passed
        if ctx.state.runtime.merge.conflicts_remaining:
            from splintercat.workflow.nodes.resolve_conflicts import (
                ResolveConflicts,
            )

            return ResolveConflicts()
        else:
            from splintercat.workflow.nodes.finalize import Finalize
            return Finalize()
