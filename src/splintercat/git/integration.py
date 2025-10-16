"""Integration between git-imerge and workspace system."""

from splintercat.git.imerge import IMerge
from splintercat.tools.parser import parse
from splintercat.tools.workspace import Workspace


def create_workspace_from_imerge(
    imerge: IMerge,
    i1: int,
    i2: int,
    workspace_id: str,
    context_lines: int = 10
) -> dict[str, Workspace]:
    """Create workspaces for all conflicts in an imerge conflict pair.

    Args:
        imerge: IMerge instance with active merge
        i1: Commit index from branch 1
        i2: Commit index from branch 2
        workspace_id: Base ID for workspace directories
        context_lines: Number of context lines before/after conflicts

    Returns:
        Dictionary mapping filepath to Workspace for each conflicted
            file

    Raises:
        ValueError: If no conflicts found or file cannot be read
    """
    # Get list of conflicted files
    conflict_files = imerge.get_conflict_files(i1, i2)

    if not conflict_files:
        raise ValueError(f"No conflicts found for ({i1}, {i2})")

    workspaces = {}

    for filepath in conflict_files:
        # Read conflicted file from working tree
        try:
            content = imerge.read_conflicted_file(filepath)
        except FileNotFoundError as e:
            raise ValueError(
                f"Conflicted file not found: {filepath}"
            ) from e

        # Parse conflicts from file
        conflicts = parse(content, context_lines=context_lines)

        if not conflicts:
            raise ValueError(
                f"No conflict markers found in {filepath}"
            )

        # For now, handle single conflict per file
        # TODO: Handle multiple conflicts per file
        if len(conflicts) > 1:
            raise ValueError(
                f"Multiple conflicts in {filepath} not yet supported"
            )

        conflict = conflicts[0]

        # Create workspace for this conflict
        # Use filepath in workspace ID for uniqueness
        safe_path = filepath.replace("/", "_").replace(".", "_")
        ws_id = f"{workspace_id}_{safe_path}"
        workspace = Workspace(conflict, ws_id)

        workspaces[filepath] = workspace

    return workspaces


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
