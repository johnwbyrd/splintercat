"""Tests for conflict workspace."""

import pytest

from splintercat.tools.parser import Conflict
from splintercat.tools.workspace import File, Tools, Workspace


@pytest.fixture
def simple_conflict():
    """Create a simple conflict for testing."""
    return Conflict(
        ours_content="our changes here",
        theirs_content="their changes here",
        base_content=None,
        context_before=["line 1", "line 2"],
        context_after=["line 3", "line 4"],
        ours_ref="HEAD",
        theirs_ref="branch",
    )


@pytest.fixture
def diff3_conflict():
    """Create a diff3 conflict with base."""
    return Conflict(
        ours_content="our version",
        theirs_content="their version",
        base_content="original version",
        context_before=["context line"],
        context_after=["more context"],
        ours_ref="HEAD",
        theirs_ref="upstream/main",
    )


def test_file_line_count():
    """Test File line_count property."""
    file = File(content="line 1\nline 2\nline 3", description="test")
    assert file.line_count == 3

    empty_file = File(content="", description="empty")
    assert empty_file.line_count == 0


def test_workspace_creation(simple_conflict):
    """Test workspace directory and file creation."""
    workspace = Workspace(simple_conflict, "test123")

    assert workspace.workdir.exists()
    assert workspace.workdir.name == "conflict_test123"

    # Check all required files exist
    assert "ours" in workspace.files
    assert "theirs" in workspace.files
    assert "before" in workspace.files
    assert "after" in workspace.files

    # Verify files written to disk
    assert (workspace.workdir / "ours").exists()
    assert (workspace.workdir / "before").exists()


def test_workspace_with_base(diff3_conflict):
    """Test workspace creation with base file (diff3)."""
    workspace = Workspace(diff3_conflict, "test_diff3")

    assert "base" in workspace.files
    assert workspace.files["base"].content == "original version"


def test_workspace_file_metadata(simple_conflict):
    """Test file metadata is correctly set."""
    workspace = Workspace(simple_conflict, "test_meta")

    # Check required flags
    assert workspace.files["before"].required is True
    assert workspace.files["after"].required is True
    assert workspace.files["ours"].required is False

    # Check descriptions contain ref names
    assert "HEAD" in workspace.files["ours"].description
    assert "branch" in workspace.files["theirs"].description


def test_list_files(simple_conflict):
    """Test list_files tool."""
    workspace = Workspace(simple_conflict, "test_list")
    tools = Tools(workspace)

    output = tools.list_files()

    assert "ours" in output
    assert "theirs" in output
    assert "before" in output
    assert "after" in output
    assert "HEAD" in output  # ours ref
    assert "branch" in output  # theirs ref
    assert "MUST" in output  # Required file indicator


def test_read_file(simple_conflict):
    """Test read_file tool."""
    workspace = Workspace(simple_conflict, "test_read")
    tools = Tools(workspace)

    # Read entire file (defaults to first 20 lines)
    output = tools.read_file("before")
    assert "1: line 1" in output
    assert "2: line 2" in output

    # Read with explicit range
    output = tools.read_file("before", start_line=1, end_line=1)
    assert "1: line 1" in output
    assert "line 2" not in output


def test_read_file_not_found(simple_conflict):
    """Test read_file with nonexistent file."""
    workspace = Workspace(simple_conflict, "test_notfound")
    tools = Tools(workspace)

    output = tools.read_file("nonexistent")
    assert "Error" in output
    assert "not found" in output


def test_write_file(simple_conflict):
    """Test write_file tool."""
    workspace = Workspace(simple_conflict, "test_write")
    tools = Tools(workspace)

    result = tools.write_file(
        "custom",
        "my custom\ncontent",
        "A custom merge"
    )

    assert "Created custom" in result
    assert "2 lines" in result
    assert "custom" in workspace.files
    assert workspace.files["custom"].content == "my custom\ncontent"
    assert (workspace.workdir / "custom").exists()


def test_cat_files(simple_conflict):
    """Test cat_files tool."""
    workspace = Workspace(simple_conflict, "test_cat")
    tools = Tools(workspace)

    # Concatenate in order: before + ours + after
    result = tools.cat_files(
        ["before", "ours", "after"],
        "resolution"
    )

    assert "Created resolution" in result
    assert "3 files" in result

    # Verify concatenation
    resolution = workspace.files["resolution"].content
    expected = (
        "line 1\nline 2\n"
        "our changes here\n"
        "line 3\nline 4"
    )
    assert resolution == expected


def test_cat_files_missing_input(simple_conflict):
    """Test cat_files with missing input file."""
    workspace = Workspace(simple_conflict, "test_cat_err")
    tools = Tools(workspace)

    result = tools.cat_files(
        ["before", "nonexistent"],
        "output"
    )

    assert "Error" in result
    assert "not found" in result


def test_submit_resolution_valid(simple_conflict):
    """Test submit_resolution with valid resolution."""
    workspace = Workspace(simple_conflict, "test_submit_ok")
    tools = Tools(workspace)

    # Create valid resolution: before + content + after
    tools.cat_files(
        ["before", "theirs", "after"],
        "resolution"
    )

    # Submit should succeed
    content = tools.submit_resolution("resolution")
    assert "line 1\nline 2" in content  # before
    assert "their changes here" in content  # theirs
    assert "line 3\nline 4" in content  # after


def test_submit_resolution_missing_before(simple_conflict):
    """Test submit_resolution rejects missing before context."""
    workspace = Workspace(simple_conflict, "test_submit_err1")
    tools = Tools(workspace)

    # Create invalid resolution (no before context)
    tools.cat_files(["ours", "after"], "bad")

    with pytest.raises(ValueError, match="must start with"):
        tools.submit_resolution("bad")


def test_submit_resolution_missing_after(simple_conflict):
    """Test submit_resolution rejects missing after context."""
    workspace = Workspace(simple_conflict, "test_submit_err2")
    tools = Tools(workspace)

    # Create invalid resolution (no after context)
    tools.cat_files(["before", "ours"], "bad")

    with pytest.raises(ValueError, match="must end with"):
        tools.submit_resolution("bad")


def test_submit_resolution_not_found(simple_conflict):
    """Test submit_resolution with nonexistent file."""
    workspace = Workspace(simple_conflict, "test_submit_err3")
    tools = Tools(workspace)

    with pytest.raises(ValueError, match="not found"):
        tools.submit_resolution("nonexistent")


def test_manual_resolution_workflow(simple_conflict):
    """Test complete manual resolution workflow."""
    workspace = Workspace(simple_conflict, "test_workflow")
    tools = Tools(workspace)

    # 1. List files to see what's available
    file_list = tools.list_files()
    assert "ours" in file_list

    # 2. Read ours and theirs to understand conflict
    ours = tools.read_file("ours")
    assert "our changes here" in ours

    theirs = tools.read_file("theirs")
    assert "their changes here" in theirs

    # 3. Decide to accept theirs
    # 4. Compose resolution
    result = tools.cat_files(
        ["before", "theirs", "after"],
        "resolution"
    )
    assert "Created resolution" in result

    # 5. Submit resolution
    content = tools.submit_resolution("resolution")

    # Verify final resolution is correct
    assert content.startswith("line 1\nline 2")
    assert "their changes here" in content
    assert content.endswith("line 3\nline 4")
