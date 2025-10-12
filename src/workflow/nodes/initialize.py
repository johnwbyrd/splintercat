"""Initialize node - start git-imerge and set up initial state."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.config import State
from src.core.log import logger
from src.git.imerge import IMerge


@dataclass
class Initialize(BaseNode[State]):
    """Initialize git-imerge merge and set up initial workflow state."""

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> "PlanStrategy":
        """Start git-imerge merge and initialize workflow state.

        Returns:
            PlanStrategy: Next node to choose merge strategy
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
                    f"git-imerge name '{imerge_name}' is already in use. "
                    f"Change 'config.git.imerge_name' in config.yaml, "
                    f"or clean up existing state with: python main.py reset --force"
                ) from e
            else:
                logger.error(f"Failed to initialize git-imerge merge: {e}")
                raise

        # Update workflow runtime state
        ctx.state.runtime.merge.current_imerge = imerge
        ctx.state.runtime.merge.status = "initialized"
        ctx.state.runtime.merge.conflicts_remaining = True

        # Log successful initialization
        logger.info(f"Initialized git-imerge merge of {source_ref} into {target_branch}")

        # Return next node
        from src.workflow.nodes.plan_strategy import PlanStrategy
        return PlanStrategy()
