"""Tests for git-imerge integration."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from splintercat.git.integration import (
    apply_resolution_to_imerge,
    create_workspace_from_imerge,
)


@pytest.fixture
def mock_imerge():
    """Create a mock IMerge instance."""
    imerge = Mock()
    imerge.workdir = Path("/tmp/test_repo")
    return imerge


def test_create_workspace_simple_conflict(mock_imerge):
    """Test creating workspace from simple conflict."""
    # Mock the imerge methods
    mock_imerge.get_conflict_files.return_value = ["test.py"]
    mock_imerge.read_conflicted_file.return_value = """line 1
line 2
<<<<<<< HEAD
our change
=======
their change
>>>>>>> branch
line 3
line 4
"""

    # Create workspaces
    workspaces = create_workspace_from_imerge(
        mock_imerge,
        i1=1,
        i2=2,
        workspace_id="test123"
    )

    # Should have one workspace for test.py
    assert len(workspaces) == 1
    assert "test.py" in workspaces

    # Check workspace contents
    workspace = workspaces["test.py"]
    assert workspace.files["ours"].content == "our change"
    assert workspace.files["theirs"].content == "their change"
    assert len(workspace.files["before"].content.splitlines()) == 2
    assert len(workspace.files["after"].content.splitlines()) == 2


def test_create_workspace_no_conflicts(mock_imerge):
    """Test error when no conflicts found."""
    mock_imerge.get_conflict_files.return_value = []

    with pytest.raises(ValueError, match="No conflicts found"):
        create_workspace_from_imerge(
            mock_imerge,
            i1=1,
            i2=2,
            workspace_id="test123"
        )


def test_create_workspace_file_not_found(mock_imerge):
    """Test error when conflicted file doesn't exist."""
    mock_imerge.get_conflict_files.return_value = ["missing.py"]
    mock_imerge.read_conflicted_file.side_effect = FileNotFoundError()

    with pytest.raises(ValueError, match="not found"):
        create_workspace_from_imerge(
            mock_imerge,
            i1=1,
            i2=2,
            workspace_id="test123"
        )


def test_create_workspace_no_markers(mock_imerge):
    """Test error when file has no conflict markers."""
    mock_imerge.get_conflict_files.return_value = ["clean.py"]
    mock_imerge.read_conflicted_file.return_value = "no conflicts here"

    with pytest.raises(ValueError, match="No conflict markers"):
        create_workspace_from_imerge(
            mock_imerge,
            i1=1,
            i2=2,
            workspace_id="test123"
        )


def test_create_workspace_multiple_conflicts(mock_imerge):
    """Test error when file has multiple conflicts (not
    supported yet).
    """
    mock_imerge.get_conflict_files.return_value = ["multi.py"]
    mock_imerge.read_conflicted_file.return_value = """
<<<<<<< HEAD
conflict 1 ours
=======
conflict 1 theirs
>>>>>>> branch
middle
<<<<<<< HEAD
conflict 2 ours
=======
conflict 2 theirs
>>>>>>> branch
"""

    with pytest.raises(ValueError, match="Multiple conflicts"):
        create_workspace_from_imerge(
            mock_imerge,
            i1=1,
            i2=2,
            workspace_id="test123"
        )


def test_apply_resolution(mock_imerge):
    """Test applying resolution back to imerge."""
    filepath = "resolved.py"
    resolution = "resolved content\nno conflicts\n"

    apply_resolution_to_imerge(mock_imerge, filepath, resolution)

    # Should write and stage the file
    mock_imerge.write_resolution.assert_called_once_with(
        filepath,
        resolution
    )
    mock_imerge.stage_file.assert_called_once_with(filepath)


def test_create_workspace_with_context(mock_imerge):
    """Test creating workspace with custom context lines."""
    mock_imerge.get_conflict_files.return_value = ["test.py"]
    mock_imerge.read_conflicted_file.return_value = """line 1
line 2
line 3
<<<<<<< HEAD
ours
=======
theirs
>>>>>>> branch
line 4
line 5
line 6
"""

    # Request only 1 line of context
    workspaces = create_workspace_from_imerge(
        mock_imerge,
        i1=1,
        i2=2,
        workspace_id="test123",
        context_lines=1
    )

    workspace = workspaces["test.py"]

    # Should have only 1 line before and after
    assert len(workspace.files["before"].content.splitlines()) == 1
    assert "line 3" in workspace.files["before"].content

    assert len(workspace.files["after"].content.splitlines()) == 1
    assert "line 4" in workspace.files["after"].content
