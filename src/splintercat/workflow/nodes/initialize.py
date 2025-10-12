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

        # Initialize IMerge wrapper
        imerge = IMerge(
            workdir=workdir,
            name=ctx.state.config.git.imerge_name,
            goal=ctx.state.config.git.imerge_goal
        )

        # Start git-imerge merge operation
        try:
            imerge.start_merge(source_ref, target_branch)
        except Exception as e:
            error_str = str(e)
            if "already in use" in error_str:
                imerge_name = ctx.state.config.git.imerge_name
                raise ValueError(
                    f"git-imerge name '{imerge_name}' is already in "
                    f"use. Change 'config.git.imerge_name' in config.yaml, "
                    f"or clean up existing state with subcommand: "
                    "reset --force"
                ) from e
            else:
                logger.error(
                    f"Failed to initialize git-imerge merge: {e}"
                )
                raise

        # Create strategy based on config
        strategy_name = ctx.state.config.strategy.name
        if strategy_name == "optimistic":
            from splintercat.strategy.optimistic import OptimisticStrategy
            strategy = OptimisticStrategy()
        elif strategy_name == "batch":
            from splintercat.strategy.batch import BatchStrategy
            batch_size = ctx.state.config.strategy.batch_size
            strategy = BatchStrategy(batch_size)
        elif strategy_name == "per_conflict":
            from splintercat.strategy.per_conflict import PerConflictStrategy
            strategy = PerConflictStrategy()
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        # Update workflow runtime state
        ctx.state.runtime.merge.current_imerge = imerge
        ctx.state.runtime.merge.status = "initialized"
        ctx.state.runtime.merge.conflicts_remaining = True
        ctx.state.runtime.merge.strategy = strategy

        # Log successful initialization
        logger.info(
            f"Initialized git-imerge merge of {source_ref} into "
            f"{target_branch} with {strategy_name} strategy"
        )

        # Return next node
        from splintercat.workflow.nodes.resolve_conflicts import (
            ResolveConflicts,
        )
        return ResolveConflicts()
