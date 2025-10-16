"""Integration between git-imerge and workspace system."""

from splintercat.git.imerge import IMerge
from splintercat.tools.workspace import Workspace


def create_workspace_from_imerge(
    imerge: IMerge,
    i1: int,
    i2: int,
    config=None
) -> Workspace:
    """Create workspace for conflicts in an imerge conflict pair.

    Args:
        imerge: IMerge instance with active merge
        i1: Commit index from branch 1
        i2: Commit index from branch 2
        config: Optional configuration object

    Returns:
        Workspace with access to git working directory and
        conflict file list

    Raises:
        ValueError: If no conflicts found
    """
    # Get list of conflicted files
    conflict_files = imerge.get_conflict_files(i1, i2)

    if not conflict_files:
        raise ValueError(f"No conflicts found for ({i1}, {i2})")

    # Create simple workspace with workdir and conflict file list
    # LLM will use git commands to investigate each conflict
    workspace = Workspace(
        workdir=imerge.workdir,
        conflict_files=conflict_files,
        config=config
    )

    return workspace


def apply_resolution_to_imerge(
    imerge: IMerge,
    filepath: str,
    resolution: str
):
    """Apply a resolved file back to git-imerge working tree.

    Args:
        imerge: IMerge instance with active merge
        filepath: Path to file being resolved
        resolution: Resolved content (no conflict markers)
    """
    # Write resolution to working tree
    imerge.write_resolution(filepath, resolution)

    # Stage the resolved file
    imerge.stage_file(filepath)
