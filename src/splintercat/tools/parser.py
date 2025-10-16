"""Parse git conflict markers into structured data."""

from dataclasses import dataclass


@dataclass
class Conflict:
    """Structured representation of a git merge conflict."""

    ours_content: str
    theirs_content: str
    base_content: str | None
    context_before: list[str]
    context_after: list[str]
    ours_ref: str
    theirs_ref: str


def parse(
    file_content: str,
    context_lines: int = 10
) -> list[Conflict]:
    """Parse git conflict markers from file content.

    Args:
        file_content: Full file content with conflict markers
        context_lines: Number of lines of context before/after
            to extract

    Returns:
        List of Conflict objects (one per conflict hunk in file)

    Raises:
        ValueError: If conflict markers are malformed
    """
    conflicts = []
    lines = file_content.splitlines(keepends=True)
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for conflict start marker
        if line.startswith("<<<<<<<"):
            conflict_start = i
            # Extract ref from marker (e.g., "<<<<<<< HEAD")
            ours_ref = line[7:].strip()

            # Check if this is diff3 format (has base marker)
            base_idx = None
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("|||||||"):
                    base_idx = j
                    break
                elif lines[j].startswith("======="):
                    # Found separator before base, so not diff3
                    break

            # Find separator
            separator_idx = None
            for j in range((base_idx if base_idx else i) + 1, len(lines)):
                if lines[j].startswith("======="):
                    separator_idx = j
                    break

            if separator_idx is None:
                raise ValueError(
                    f"Malformed conflict at line {i}: "
                    f"no separator found"
                )

            # Find end marker
            end_idx = None
            theirs_ref = None
            for j in range(separator_idx + 1, len(lines)):
                if lines[j].startswith(">>>>>>>"):
                    end_idx = j
                    # Extract ref from marker
                    theirs_ref = lines[j][7:].strip()
                    break

            if end_idx is None:
                raise ValueError(
                    f"Malformed conflict at line {i}: "
                    f"no end marker found"
                )

            # Extract content based on format
            if base_idx is not None:
                # diff3 format: ours | base | theirs
                ours_content = "".join(lines[i + 1:base_idx])
                base_content = "".join(lines[base_idx + 1:separator_idx])
                theirs_content = "".join(lines[separator_idx + 1:end_idx])
            else:
                # standard 3-way: ours | theirs
                ours_content = "".join(lines[i + 1:separator_idx])
                base_content = None
                theirs_content = "".join(lines[separator_idx + 1:end_idx])

            # Extract context before conflict
            context_start = max(0, conflict_start - context_lines)
            context_before = [
                line.rstrip('\n\r')
                for line in lines[context_start:conflict_start]
            ]

            # Extract context after conflict
            context_end = min(len(lines), end_idx + 1 + context_lines)
            context_after = [
                line.rstrip('\n\r')
                for line in lines[end_idx + 1:context_end]
            ]

            # Create Conflict object
            conflicts.append(Conflict(
                ours_content=ours_content.rstrip('\n\r'),
                theirs_content=theirs_content.rstrip('\n\r'),
                base_content=(
                    base_content.rstrip('\n\r')
                    if base_content else None
                ),
                context_before=context_before,
                context_after=context_after,
                ours_ref=ours_ref or "ours",
                theirs_ref=theirs_ref or "theirs",
            ))

            # Move past this conflict
            i = end_idx + 1
        else:
            i += 1

    return conflicts
