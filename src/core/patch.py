"""Patch value object with lazy-computed properties."""

import re
from dataclasses import dataclass, field
from functools import cached_property


@dataclass
class Patch:
    """Represents a single patch with metadata.

    Patches are created from git format-patch output and contain the full
    patch text along with parsed metadata.

    Attributes:
        id: Git commit hash or unique identifier
        diff: Full patch text (mbox format from git format-patch)
        metadata: Extensible metadata storage for additional context
    """

    id: str
    diff: str
    metadata: dict = field(default_factory=dict)

    @cached_property
    def author(self) -> str:
        """Parse and return patch author from From: header.

        Returns:
            Author name and email, or "Unknown" if not found
        """
        match = re.search(r"^From:\s*(.+)$", self.diff, re.MULTILINE)
        return match.group(1).strip() if match else "Unknown"

    @cached_property
    def changed_files(self) -> list[str]:
        """Parse and return list of changed files from diff headers.

        Returns:
            List of file paths that were modified in this patch
        """
        files = []
        # Match both "diff --git a/path b/path" and "+++ b/path" lines
        pattern = r"^(?:diff --git a/(\S+)|^\+\+\+ b/(\S+))"
        for match in re.finditer(pattern, self.diff, re.MULTILINE):
            file_path = match.group(1) or match.group(2)
            if file_path and file_path != "/dev/null" and file_path not in files:
                files.append(file_path)
        return files

    @cached_property
    def timestamp(self) -> str:
        """Parse and return patch timestamp from Date: header.

        Returns:
            Date string, or empty string if not found
        """
        match = re.search(r"^Date:\s*(.+)$", self.diff, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @cached_property
    def subject(self) -> str:
        """Parse and return patch subject from Subject: header.

        Returns:
            Subject line, or empty string if not found
        """
        match = re.search(r"^Subject:\s*(.+)$", self.diff, re.MULTILINE)
        return match.group(1).strip() if match else ""
