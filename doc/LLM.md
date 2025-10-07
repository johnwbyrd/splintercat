# Instructions for LLMs

## Development Environment

- **Virtual environment** - Python tools are in `../.venv/bin/` - source `../.venv/bin/activate` before running ruff, python, pip, etc.

## Git Repository Structure

The llvm-mos repository has multiple remotes for testing:

- **upstream/main** - llvm-mos official branch (READ ONLY - never modify)
- **heaven/main** - llvm official repository (READ ONLY - never modify)
- **stable-test** - Test branch, should be deleted and recreated from upstream/main for each test run

## Code Style

- **NO EMOJIS** - Do not use emojis anywhere in code, comments, docstrings, commit messages, or markdown files

## Documentation Style

- **NO CODE in Markdown** - Do not put Python code blocks in design documents or any markdown files
- **Markdown is for prose** - Design documents contain descriptions and explanations only
- **Function interfaces OK** - Brief interface specifications are acceptable (methods, parameters, return types)
- **Keep it concise** - Describe what components do, not how they're implemented

## Examples

**Good - Function Interface:**
```
Source ABC:
- get_patches() → PatchSet
```

**Bad - Full Code:**
```python
class Source(ABC):
    @abstractmethod
    def get_patches(self) -> PatchSet:
        """Fetch patches from the source."""
        raise NotImplementedError
```

**Good - Prose Description:**
"Strategy is a pure function that analyzes State and returns the next PatchSet to try, or None when done."

**Bad - Code Example:**
"Here's how SequentialStrategy works: [50 lines of Python code]"

## Summary

- Code belongs in `.py` files
- Markdown belongs in `.md` files
- Keep them separate
- No emojis anywhere
- No code blocks in markdown
