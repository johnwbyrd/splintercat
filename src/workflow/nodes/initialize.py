"""Initialize node - start git-imerge and set up initial state."""

from __future__ import annotations
from pathlib import Path

from dataclasses import dataclass

from pydantic_graph import BaseNode, GraphRunContext

from src.core.log import logger
from src.git.imerge import IMerge
from src.state.workflow import MergeWorkflowState


@dataclass
class Initialize(BaseNode[MergeWorkflowState]):
    """Initialize git-imerge merge and set up initial workflow state."""

    async def run(
        self, ctx: GraphRunContext[MergeWorkflowState]
    ) -> "PlanStrategy":
        """Start git-imerge merge and initialize workflow state.

        Returns:
            PlanStrategy: Next node to choose merge strategy
        """
        # Get configuration from state
        settings = ctx.state.settings
        source_ref = settings.source.ref
        target_branch = settings.target.branch
        workdir = Path(settings.target.workdir) if settings.target.workdir else None

        # Initialize IMerge wrapper
        imerge = IMerge(
            workdir=workdir or Path.cwd(),
            name=settings.imerge.name,
            goal=settings.imerge.goal
        )

        # Start git-imerge merge operation
        try:
            imerge.start_merge(source_ref, target_branch)
        except Exception as e:
            error_str = str(e)
            if "already in use" in error_str:
                raise ValueError(f"git-imerge name '{settings.imerge.name}' is already in use. "
                               f"Change 'imerge.name' in config.yaml, or run 'git imerge list' and "
                               f"'git imerge remove {settings.imerge.name} --force' if safe to clean up.")
            else:
                logger.error(f"Failed to initialize git-imerge merge: {e}")
                raise

        # Update workflow state
        ctx.state.imerge = imerge
        ctx.state.imerge_name = imerge.name
        ctx.state.status = "initialized"
        ctx.state.conflicts_remaining = True

        # Log successful initialization
        logger.info(f"Initialized git-imerge merge of {source_ref} into {target_branch}")

        # Return next node
        from src.workflow.nodes.plan_strategy import PlanStrategy
        return PlanStrategy()
