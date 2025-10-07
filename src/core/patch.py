"""Patch value object with lazy-computed properties."""

import re
from dataclasses import dataclass, field
from functools import cached_property


@dataclass
class Patch:
    """Represents a single commit for cherry-picking with metadata.

    Patches contain commit SHAs and metadata for cherry-picking.
    Diff text is optional and only used for analysis.

    Attributes:
        id: Git commit hash or unique identifier
        diff: Optional patch text (empty string if not needed for cherry-pick)
        metadata: Extensible metadata storage (subject, from, date, etc.)
    """

    id: str
    diff: str = ""
    metadata: dict = field(default_factory=dict)

    @cached_property
    def author(self) -> str:
        """Parse and return patch author.

        First checks metadata (populated from git show), then falls back to
        parsing diff text if available.

        Returns:
            Author name and email, or "Unknown" if not found
        """
        if "from" in self.metadata:
            return self.metadata["from"]
        if self.diff:
            match = re.search(r"^From:\s*(.+)$", self.diff, re.MULTILINE)
            return match.group(1).strip() if match else "Unknown"
        return "Unknown"

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
        """Parse and return patch timestamp.

        First checks metadata (populated from git show), then falls back to
        parsing diff text if available.

        Returns:
            Date string, or empty string if not found
        """
        if "date" in self.metadata:
            return self.metadata["date"]
        if self.diff:
            match = re.search(r"^Date:\s*(.+)$", self.diff, re.MULTILINE)
            return match.group(1).strip() if match else ""
        return ""

    @cached_property
    def subject(self) -> str:
        """Parse and return patch subject.

        First checks metadata (populated from git show), then falls back to
        parsing diff text if available.

        Returns:
            Subject line, or empty string if not found
        """
        if "subject" in self.metadata:
            return self.metadata["subject"]
        if self.diff:
            match = re.search(r"^Subject:\s*(.+)$", self.diff, re.MULTILINE)
            return match.group(1).strip() if match else ""
        return ""
