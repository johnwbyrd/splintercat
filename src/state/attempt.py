"""Merge attempt tracking."""

from pydantic import BaseModel

from src.state.build import BuildResult
from src.state.conflict import ConflictResolution


class MergeAttempt(BaseModel):
    """Record of a single merge attempt."""

    attempt_number: int
    strategy: str
    conflicts_resolved: list[ConflictResolution]
    build_result: BuildResult | None
    failure_summary: str | None
    planner_decision: str | None
