"""Main workflow state for graph."""

from pathlib import Path

from pydantic import BaseModel

from src.state.attempt import MergeAttempt
from src.state.conflict import ConflictInfo, ConflictResolution


class MergeWorkflowState(BaseModel):
    """State container for the merge workflow.

    This is the main state object that flows through the graph state machine.
    """

    imerge_name: str
    workdir: Path
    source_ref: str
    target_branch: str
    current_strategy: str
    conflicts_in_batch: list[ConflictInfo]
    attempts: list[MergeAttempt]
    resolutions: list[ConflictResolution]
    status: str
