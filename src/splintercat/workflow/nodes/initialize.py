"""Initialize node - start git-imerge and set up initial state."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from splintercat.core.config import State
from splintercat.core.log import logger
from splintercat.git.imerge import IMerge


@dataclass
class Initialize(BaseNode[State]):
    """Initialize git-imerge merge and set up initial workflow
    state."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "ResolveConflicts":
        """Start git-imerge merge and initialize workflow state.

        Returns:
            ResolveConflicts: Next node to resolve conflicts
        """
        # Get configuration from state
        source_ref = ctx.state.config.git.source_ref
        target_branch = ctx.state.config.git.target_branch
        workdir = ctx.state.config.git.target_workdir

        # Get merge name for logging directory structure
        merge_name = ctx.state.config.git.imerge_name

        # Setup logging and log directory management
        logger.setup(
            min_log_level=ctx.state.config.log_level,
            log_root=ctx.state.config.log_root,
            merge_name=merge_name
        )

        # Store reference to log manager in state
        ctx.state.runtime.merge.log_manager = logger.log_manager

        # Initialize IMerge wrapper
        imerge = IMerge(
            workdir=workdir,
            name=ctx.state.config.git.imerge_name,
            goal=ctx.state.config.git.imerge_goal,
            config=ctx.state.config
        )

        # Check if merge already exists and load it, otherwise
        # start new
        imerge_name = ctx.state.config.git.imerge_name
        is_resuming = IMerge.exists(workdir, imerge_name)

        if is_resuming:
            logger.info(
                f"Resuming existing imerge '{imerge_name}'"
            )
            imerge.load_existing()
        else:
            logger.info(
                f"Starting new imerge '{imerge_name}'"
            )
            imerge.start_merge(source_ref, target_branch)

        # Update workflow runtime state
        ctx.state.runtime.merge.current_imerge = imerge
        ctx.state.runtime.merge.status = "initialized"
        ctx.state.runtime.merge.conflicts_remaining = True

        # Log successful initialization
        action = "Resumed" if is_resuming else "Initialized"
        logger.info(
            f"{action} git-imerge merge of {source_ref} into "
            f"{target_branch}"
        )

        # Return next node
        from splintercat.workflow.nodes.resolve_conflicts import (
            ResolveConflicts,
        )
        return ResolveConflicts()
