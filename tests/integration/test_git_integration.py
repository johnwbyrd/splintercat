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

    # Create workspace with new simplified API
    workspace = create_workspace_from_imerge(
        mock_imerge,
        i1=1,
        i2=2
    )

    # Check workspace has correct attributes
    assert workspace.workdir == mock_imerge.workdir
    assert workspace.conflict_files == ["test.py"]


def test_create_workspace_no_conflicts(mock_imerge):
    """Test error when no conflicts found."""
    mock_imerge.get_conflict_files.return_value = []

    with pytest.raises(ValueError, match="No conflicts found"):
        create_workspace_from_imerge(
            mock_imerge,
            i1=1,
            i2=2
        )


def test_create_workspace_with_multiple_files(mock_imerge):
    """Test workspace with multiple conflicted files."""
    mock_imerge.get_conflict_files.return_value = [
        "file1.py",
        "file2.py",
        "file3.py"
    ]

    workspace = create_workspace_from_imerge(
        mock_imerge,
        i1=1,
        i2=2
    )

    # Should have all three files in conflict_files list
    assert len(workspace.conflict_files) == 3
    assert "file1.py" in workspace.conflict_files
    assert "file2.py" in workspace.conflict_files
    assert "file3.py" in workspace.conflict_files


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


def test_create_workspace_with_config(mock_imerge):
    """Test creating workspace with config object."""
    mock_imerge.get_conflict_files.return_value = ["test.py"]

    # Create mock config
    mock_config = Mock()

    workspace = create_workspace_from_imerge(
        mock_imerge,
        i1=1,
        i2=2,
        config=mock_config
    )

    # Should pass config to workspace
    assert workspace.config == mock_config
