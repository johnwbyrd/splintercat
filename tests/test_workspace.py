"""Tests for workspace tools (command-based API)."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.tools.workspace import (
    Workspace,
    concatenate_to_file,
    read_file,
    submit_resolution,
    write_file,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test files."""
    # Create a workspace with some test files
    (tmp_path / "test.py").write_text("line 1\nline 2\nline 3\n")
    (tmp_path / "conflict.py").write_text(
        "before\n<<<<<<< HEAD\nours\n=======\ntheirs\n"
        ">>>>>>> branch\nafter\n"
    )

    workspace = Workspace(
        workdir=tmp_path,
        conflict_files=["conflict.py"]
    )
    return workspace


@pytest.fixture
def mock_ctx(temp_workspace):
    """Create a mock RunContext with workspace."""
    ctx = Mock(spec=RunContext)
    ctx.deps = temp_workspace
    return ctx


def test_workspace_creation():
    """Test creating a workspace."""
    workdir = Path("/tmp/test")
    conflict_files = ["file1.py", "file2.py"]

    workspace = Workspace(
        workdir=workdir,
        conflict_files=conflict_files
    )

    assert workspace.workdir == workdir
    assert workspace.conflict_files == conflict_files
    assert workspace.config is None


def test_workspace_with_config():
    """Test creating workspace with config."""
    workdir = Path("/tmp/test")
    mock_config = Mock()

    workspace = Workspace(
        workdir=workdir,
        conflict_files=["test.py"],
        config=mock_config
    )

    assert workspace.config == mock_config


def test_read_file_basic(mock_ctx, temp_workspace):
    """Test reading a file with line numbers."""
    output = read_file(mock_ctx, "test.py")

    # Should have line numbers
    assert "1: line 1" in output
    assert "2: line 2" in output
    assert "3: line 3" in output


def test_read_file_with_range(mock_ctx, temp_workspace):
    """Test reading specific line range."""
    # Read lines 2-3
    output = read_file(mock_ctx, "test.py", start_line=2, num_lines=2)

    assert "2: line 2" in output
    assert "3: line 3" in output
    assert "1: line 1" not in output


def test_read_file_entire_file(mock_ctx, temp_workspace):
    """Test reading entire file with num_lines=-1."""
    output = read_file(mock_ctx, "test.py", start_line=1, num_lines=-1)

    assert "1: line 1" in output
    assert "2: line 2" in output
    assert "3: line 3" in output


def test_read_file_not_found(mock_ctx):
    """Test reading nonexistent file raises ModelRetry."""
    with pytest.raises(ModelRetry, match="not found"):
        read_file(mock_ctx, "nonexistent.py")


def test_write_file_basic(mock_ctx, temp_workspace):
    """Test writing a new file."""
    content = "new content\nline 2\n"

    result = write_file(mock_ctx, "new.py", content)

    # Check return message
    assert "Wrote" in result
    assert "2 lines" in result
    assert "new.py" in result

    # Verify file was written
    written_path = temp_workspace.workdir / "new.py"
    assert written_path.exists()
    assert written_path.read_text() == content


def test_write_file_creates_directories(mock_ctx, temp_workspace):
    """Test writing file creates parent directories."""
    content = "test content\n"

    result = write_file(mock_ctx, "subdir/nested/file.py", content)

    assert "Wrote" in result

    # Verify directory and file created
    written_path = temp_workspace.workdir / "subdir" / "nested" / "file.py"
    assert written_path.exists()
    assert written_path.read_text() == content


def test_write_file_replaces_existing(mock_ctx, temp_workspace):
    """Test writing over existing file replaces it."""
    new_content = "replaced content\n"

    result = write_file(mock_ctx, "test.py", new_content)

    assert "Wrote" in result

    # Verify file was replaced
    file_path = temp_workspace.workdir / "test.py"
    assert file_path.read_text() == new_content


def test_concatenate_to_file_basic(mock_ctx, temp_workspace):
    """Test concatenating multiple files."""
    # Create source files
    (temp_workspace.workdir / "part1.txt").write_text("part 1")
    (temp_workspace.workdir / "part2.txt").write_text("part 2")
    (temp_workspace.workdir / "part3.txt").write_text("part 3")

    result = concatenate_to_file(
        mock_ctx,
        "combined.txt",
        ["part1.txt", "part2.txt", "part3.txt"]
    )

    assert "Created combined.txt" in result
    assert "3 source files" in result

    # Verify concatenation
    combined_path = temp_workspace.workdir / "combined.txt"
    assert combined_path.exists()
    content = combined_path.read_text()
    assert content == "part 1\npart 2\npart 3"


def test_concatenate_to_file_missing_source(mock_ctx):
    """Test concatenate with missing source file."""
    with pytest.raises(ModelRetry, match="not found"):
        concatenate_to_file(
            mock_ctx,
            "output.txt",
            ["missing.txt"]
        )


def test_submit_resolution_valid(mock_ctx, temp_workspace):
    """Test submitting a valid resolution."""
    # Write a resolved file (no conflict markers, valid Python)
    resolved = "# Resolved file\nresult = 42\n"
    (temp_workspace.workdir / "resolved.py").write_text(resolved)

    result = submit_resolution(mock_ctx, "resolved.py")

    assert "Resolution validated" in result
    assert "resolved.py" in result


def test_submit_resolution_with_conflict_markers(mock_ctx, temp_workspace):
    """Test submitting file with conflict markers fails."""
    # File still has conflict markers
    with pytest.raises(ModelRetry, match="conflict marker"):
        submit_resolution(mock_ctx, "conflict.py")


def test_submit_resolution_empty_file(mock_ctx, temp_workspace):
    """Test submitting empty file requires confirmation."""
    (temp_workspace.workdir / "empty.py").write_text("")

    # Should fail without confirmation
    with pytest.raises(ModelRetry, match="empty"):
        submit_resolution(mock_ctx, "empty.py")

    # Should succeed with confirmation
    result = submit_resolution(
        mock_ctx,
        "empty.py",
        confirm_empty=True
    )
    assert "validated" in result


def test_submit_resolution_python_syntax_error(mock_ctx, temp_workspace):
    """Test Python syntax checking."""
    bad_python = "def foo(\n  invalid syntax"
    (temp_workspace.workdir / "bad.py").write_text(bad_python)

    with pytest.raises(ModelRetry, match="Python syntax error"):
        submit_resolution(mock_ctx, "bad.py")


def test_submit_resolution_python_valid(mock_ctx, temp_workspace):
    """Test valid Python passes syntax check."""
    good_python = "def foo():\n    return 42\n"
    (temp_workspace.workdir / "good.py").write_text(good_python)

    result = submit_resolution(mock_ctx, "good.py")
    assert "validated" in result


def test_submit_resolution_json_syntax_error(mock_ctx, temp_workspace):
    """Test JSON syntax checking."""
    bad_json = '{"key": invalid}'
    (temp_workspace.workdir / "bad.json").write_text(bad_json)

    with pytest.raises(ModelRetry, match="JSON syntax error"):
        submit_resolution(mock_ctx, "bad.json")


def test_submit_resolution_json_valid(mock_ctx, temp_workspace):
    """Test valid JSON passes syntax check."""
    good_json = '{"key": "value", "number": 42}'
    (temp_workspace.workdir / "good.json").write_text(good_json)

    result = submit_resolution(mock_ctx, "good.json")
    assert "validated" in result


def test_submit_resolution_yaml_syntax_error(mock_ctx, temp_workspace):
    """Test YAML syntax checking."""
    bad_yaml = "key: value\n  invalid: indentation\n"
    (temp_workspace.workdir / "bad.yaml").write_text(bad_yaml)

    with pytest.raises(ModelRetry, match="YAML syntax error"):
        submit_resolution(mock_ctx, "bad.yaml")


def test_submit_resolution_yaml_valid(mock_ctx, temp_workspace):
    """Test valid YAML passes syntax check."""
    good_yaml = "key: value\nnested:\n  item: 42\n"
    (temp_workspace.workdir / "good.yaml").write_text(good_yaml)

    result = submit_resolution(mock_ctx, "good.yaml")
    assert "validated" in result


def test_submit_resolution_skip_syntax_check(mock_ctx, temp_workspace):
    """Test skipping syntax validation."""
    bad_python = "def invalid syntax"
    (temp_workspace.workdir / "skip.py").write_text(bad_python)

    # Should succeed when skipping syntax check
    result = submit_resolution(
        mock_ctx,
        "skip.py",
        skip_syntax_check=True
    )
    assert "validated" in result


def test_submit_resolution_deleted_file(mock_ctx, temp_workspace):
    """Test submitting a file that doesn't exist (deleted)."""
    result = submit_resolution(mock_ctx, "deleted.py")

    assert "does not exist" in result
    assert "deleted" in result


def test_complete_resolution_workflow(mock_ctx, temp_workspace):
    """Test complete workflow: read, write, submit."""
    # 1. Read conflicted file
    conflict_content = read_file(mock_ctx, "conflict.py")
    assert "<<<<<<< HEAD" in conflict_content

    # 2. Write resolved version
    resolved = "before\nresolved\nafter\n"
    write_result = write_file(mock_ctx, "conflict.py", resolved)
    assert "Wrote" in write_result

    # 3. Submit resolution
    submit_result = submit_resolution(mock_ctx, "conflict.py")
    assert "validated" in submit_result

    # Verify final file content
    final_content = (temp_workspace.workdir / "conflict.py").read_text()
    assert final_content == resolved
    assert "<<<<<<< HEAD" not in final_content
