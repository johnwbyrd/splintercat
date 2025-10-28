# Instructions for LLMs

The following constitute instructions for Claude, OpenAI, Cline, and other LLM-based coding systems.

## Code Style

- **SCREW BACKWARDS COMPATIBILITY** - Do NOT engineer for backwards compatibility.  BREAK AND REWRITE CODE TOTALLY FROM SCRATCH IF NEEDED, using a superior design and structure.  There are NO existing users.  Doing something "for backwards compatibility" is an anti-pattern.  If you ignore this part and propose something for backwards compatibility, THE USER WILL EMBARRASS YOU BY FORCING YOU TO READ THIS PARAGRAPH AGAIN.

- **NO EMOJIS** - Do not use emojis anywhere in code, comments, docstrings, commit messages, or markdown files

- **WRITE THE LEAST AMOUNT OF CODE POSSIBLE** - Much of the functionality we need already exists in Pydantic or other Python libraries. USE THEM. Do not reinvent the wheel. Especially, do not be afraid of deleting code! Removing dead or unclear code from this design is Zen engineering and we love to do it. YAGNI.

- Observe PEP 8 as religion. Especially be aware of the 79 character line limit and 72 on docstrings. ruff check will check you on this.

- Document code flow using debug messages.  We use a simple wrapper around logfire in log.py. Do not refer to logfire directly in the code. Use spans when documenting long-running processes and complex sequences.

## Implementation Timing

- **DO NOT implement until needed** - Wait for real-world merge cases that simpler tools cannot handle
- **DESIGN.md is source of truth** - Architecture is designed and documented in doc/DESIGN.md
- **Configuration-driven** - Settings belong in config.yaml, not hardcoded in Python
- **Prove it works first** - Build MVP, test on real data, learn from failures

## File Reading Requirements

When instructed to read all files in this project or codebase:

- **Read EVERY .md, .py, and .toml file** - Do not selectively prioritize "core" or "architectural" files. Read all files mentioned, including utilities, imports, empty files, test files, and configuration files.  Use the read_multiple_files tool to make this process efficient.
- **Complete before proceeding** - Do not proceed to analysis, planning, or testing until ALL files have been read.
- **No assumptions about importance** - Even seemingly minor files can contain critical details or dependencies. Assumption of irrelevance is not permitted.
- **Account for volume** - If the set is very large (dozens of files), explain the scope challenge explicitly and request prioritization guidance rather than arbitrarily reducing coverage.
- **Document what was read** - Keep accurate track of what has and hasn't been read. Claims of "all done" must be truthful to avoid incomplete knowledge affecting downstream tasks.

## Git Repository Structure

The llvm-mos repository has multiple remotes for testing:

- **upstream/main** - llvm-mos official branch (READ ONLY - never modify)
- **heaven/main** - llvm official repository (READ ONLY - never modify)
- **stable-test** - Test branch, should be deleted and recreated from upstream/main for each test run

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

## Development Environment

- IMPORTANT: If you're running within Cline, and you need to run a command-line tool, use the mcp-cli-exec MCP tool instead of the built-in tool.  The mcp-cli-exec tool is much more stable and dependable.

- **Virtual environment** - Python tools are in `../.venv/bin/` - you may need to source `../.venv/bin/activate` before running ruff, python, pip, etc. If you need some new Python package, update pyproject.toml .

- **Install in editable mode:**

```bash
source ../.venv/bin/activate
pip install -e .[dev]
```

- **Running tests:**

```bash
source ../.venv/bin/activate
pytest                    # All tests
pytest tests/test_checkrunner.py -v  # Just CheckRunner
ruff check                # Linting
pytest -v                 # Checking
```

Run ruff check and pytest -v after every major change, and fix problems.

## Summary

- Code belongs in `.py` files
- Markdown belongs in `.md` files
- Keep them separate
- No emojis anywhere
- No code blocks in markdown
- Don't implement until we encounter problems that require the solution
