"""Tests for conflict parser."""

import pytest

from splintercat.tools.parser import parse


def test_parse_simple_conflict():
    """Test parsing a simple 3-way conflict."""
    content = """line 1
line 2
<<<<<<< HEAD
our change
=======
their change
>>>>>>> branch
line 3
line 4
"""
    conflicts = parse(content, context_lines=2)

    assert len(conflicts) == 1
    conflict = conflicts[0]

    assert conflict.ours_content == "our change"
    assert conflict.theirs_content == "their change"
    assert conflict.base_content is None
    assert conflict.context_before == ["line 1", "line 2"]
    assert conflict.context_after == ["line 3", "line 4"]
    assert conflict.ours_ref == "HEAD"
    assert conflict.theirs_ref == "branch"


def test_parse_diff3_format():
    """Test parsing diff3 format with base section."""
    content = """line 1
<<<<<<< HEAD
our change
||||||| base
original code
=======
their change
>>>>>>> branch
line 2
"""
    conflicts = parse(content, context_lines=1)

    assert len(conflicts) == 1
    conflict = conflicts[0]

    assert conflict.ours_content == "our change"
    assert conflict.theirs_content == "their change"
    assert conflict.base_content == "original code"
    assert conflict.context_before == ["line 1"]
    assert conflict.context_after == ["line 2"]


def test_parse_multiple_conflicts():
    """Test parsing multiple conflicts in one file."""
    content = """line 1
<<<<<<< HEAD
change 1 ours
=======
change 1 theirs
>>>>>>> branch
middle line
<<<<<<< HEAD
change 2 ours
=======
change 2 theirs
>>>>>>> branch
last line
"""
    conflicts = parse(content, context_lines=1)

    assert len(conflicts) == 2

    assert conflicts[0].ours_content == "change 1 ours"
    assert conflicts[0].theirs_content == "change 1 theirs"
    assert conflicts[0].context_before == ["line 1"]
    assert conflicts[0].context_after == ["middle line"]

    assert conflicts[1].ours_content == "change 2 ours"
    assert conflicts[1].theirs_content == "change 2 theirs"
    assert conflicts[1].context_before == ["middle line"]
    assert conflicts[1].context_after == ["last line"]


def test_parse_empty_sections():
    """Test parsing conflict with empty sections."""
    content = """line 1
<<<<<<< HEAD
=======
their addition
>>>>>>> branch
line 2
"""
    conflicts = parse(content)

    assert len(conflicts) == 1
    conflict = conflicts[0]

    assert conflict.ours_content == ""
    assert conflict.theirs_content == "their addition"


def test_parse_multiline_conflict():
    """Test parsing conflict with multiple lines in each section."""
    content = """context
<<<<<<< HEAD
our line 1
our line 2
our line 3
=======
their line 1
their line 2
>>>>>>> upstream/main
more context
"""
    conflicts = parse(content, context_lines=1)

    assert len(conflicts) == 1
    conflict = conflicts[0]

    assert conflict.ours_content == "our line 1\nour line 2\nour line 3"
    assert conflict.theirs_content == "their line 1\ntheir line 2"
    assert conflict.context_before == ["context"]
    assert conflict.context_after == ["more context"]
    assert conflict.theirs_ref == "upstream/main"


def test_parse_no_conflicts():
    """Test parsing file with no conflicts."""
    content = """line 1
line 2
line 3
"""
    conflicts = parse(content)

    assert len(conflicts) == 0


def test_parse_malformed_no_separator():
    """Test that malformed conflict raises error."""
    content = """line 1
<<<<<<< HEAD
our change
>>>>>>> branch
"""
    with pytest.raises(ValueError, match="no separator found"):
        parse(content)


def test_parse_malformed_no_end():
    """Test that malformed conflict raises error."""
    content = """line 1
<<<<<<< HEAD
our change
=======
their change
"""
    with pytest.raises(ValueError, match="no end marker found"):
        parse(content)


def test_parse_zero_context():
    """Test parsing with zero context lines."""
    content = """line 1
line 2
<<<<<<< HEAD
our change
=======
their change
>>>>>>> branch
line 3
line 4
"""
    conflicts = parse(content, context_lines=0)

    assert len(conflicts) == 1
    conflict = conflicts[0]

    assert conflict.context_before == []
    assert conflict.context_after == []


def test_parse_at_file_boundaries():
    """Test conflict at start and end of file."""
    content = """<<<<<<< HEAD
our start
=======
their start
>>>>>>> branch
middle
<<<<<<< HEAD
our end
=======
their end
>>>>>>> branch"""

    conflicts = parse(content, context_lines=5)

    assert len(conflicts) == 2
    assert conflicts[0].context_before == []
    assert conflicts[1].context_after == []
