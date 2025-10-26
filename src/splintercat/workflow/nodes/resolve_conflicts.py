"""ResolveConflicts node - resolve conflicts using resolver model."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger
from splintercat.git.integration import (
    create_workspace_from_imerge,
)
from splintercat.model.resolver import resolve_workspace


@dataclass
class ResolveConflicts(BaseNode[State]):
    """Resolve conflicts using resolver model."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "Check":
        """Resolve exactly one conflict using resolver model.

        Uses error context from last failed check if retrying.

        Returns:
            Check: Always run checks after resolving one conflict
        """
        # Increment iteration (new resolve-check cycle)
        ctx.state.runtime.merge.iteration += 1
        logger.set_iteration(ctx.state.runtime.merge.iteration)

        imerge = ctx.state.runtime.merge.current_imerge

        if not imerge:
            raise ValueError("No active imerge instance")

        # Get failure context from last check if retrying
        failure_context = None
        if ctx.state.runtime.merge.retry_count > 0:
            last_check = ctx.state.runtime.merge.last_failed_check
            if last_check:
                failure_context = (
                    f"Check '{last_check.check_name}' failed with "
                    f"returncode {last_check.returncode}. "
                    f"See log: {last_check.log_file}"
                )

        # Get current conflict
        conflict_pair = imerge.get_current_conflict()

        if conflict_pair is None:
            # No more conflicts
            logger.info("No more conflicts to resolve")
            ctx.state.runtime.merge.conflicts_remaining = False
        else:
            # Resolve exactly one conflict
            i1, i2 = conflict_pair
            logger.info(f"Resolving conflict pair ({i1}, {i2})")

            # Create workspace for this conflict pair
            workspace = create_workspace_from_imerge(
                imerge, i1, i2, config=ctx.state.config
            )

            # Resolve all conflicts in this pair
            # LLM has access to all files via commands
            await resolve_workspace(
                workspace,
                llm_config=ctx.state.config.llm,
                failure_context=failure_context,
            )

            # Stage all resolved files
            # (stage_file handles case where files are already staged)
            for filepath in workspace.conflict_files:
                logger.info(f"Staging resolved file: {filepath}")
                imerge.stage_file(filepath)

            # Continue imerge after resolving all files in this pair
            imerge.continue_after_resolution()

            # Check if more conflicts remain
            next_conflict = imerge.get_current_conflict()
            ctx.state.runtime.merge.conflicts_remaining = (
                next_conflict is not None
            )

        # Return Check node
        from splintercat.workflow.nodes.check import Check

        # Determine which checks to run
        # TODO: Make this configurable
        check_names = list(ctx.state.config.check.commands.keys())
        return Check(check_names=check_names)
