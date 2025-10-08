# Merge Resolver Design - File-Based Conflict Resolution

## Problem Statement

Traditional LLM approaches to merge conflict resolution fail because they require the LLM to regenerate entire files. This is:

- **Expensive**: Large files cost many tokens to regenerate
- **Error-prone**: LLMs make typos, miss details, or change unrelated code
- **Slow**: Generating 8,000+ lines takes significant time
- **Wasteful**: Most of the file is unchanged, only small conflict sections need resolution

### Real-World Example

File: llvm/tools/llvm-readobj/ELFDumper.cpp
- Size: 8,896 lines
- Conflicts: 1 conflict at line 1139 (80 lines of enum entries)
- Problem: LLM must regenerate 8,896 lines perfectly to resolve an 80-line conflict

## Solution: File-Based Composition

Instead of treating the LLM as a text generator, treat it as an **analyst working with files**.

### Core Insight

Merge conflict resolution is fundamentally about **selecting and concatenating sections**:
- Choose which version (base, ours, theirs) to use
- Combine sections in the right order
- Preserve surrounding context

This maps naturally to file operations:
- Each conflict section is a separate file
- Resolution is file concatenation
- Simple, composable, debuggable

### Unix Philosophy

The design follows Unix principles:
- Small, focused tools that do one thing well
- Files as the primary interface
- Composition through concatenation
- Human-readable intermediate artifacts

## Integration with git-imerge

Splintercat uses git-imerge to subdivide large merges into pairwise commit merges. The resolver operates within this framework:

### Conflict Granularity

git-imerge provides:
- Conflict pairs: (i1, i2) representing one commit from each branch
- Multiple files may have conflicts in a single pair
- Multiple hunks may exist within a single file

The resolver processes:
1. Each conflict pair from git-imerge
2. Each file with conflicts in that pair
3. Each hunk within each file

### Workflow Integration

```
git-imerge identifies conflict pair (i1, i2)
  ↓
For each file with conflicts:
  ↓
  For each hunk in file:
    ↓
    Create conflict workspace with files
    ↓
    LLM: Read files → Investigate → Compose resolution → Submit
    ↓
  Apply resolution to actual file
  ↓
git-imerge continue (advances to next conflict pair)
```

### State Preservation

git-imerge maintains state in refs/imerge/name/, allowing:
- Resume after interruption
- Track which commit pairs are complete
- Bisect to find problematic merges

The resolver leverages this by coordinating with the strategy system to decide when to build/test.

## Conflict Workspace

For each conflict hunk, we create a workspace directory containing files that represent the conflict.

### Workspace Structure

```
/tmp/conflict_<id>/
  base.txt         - Content from merge base (common ancestor)
  ours.txt         - Content from our branch (HEAD)
  theirs.txt       - Content from their branch (incoming)
  before.txt       - Context before conflict (required in resolution)
  after.txt        - Context after conflict (required in resolution)

  [LLM can create additional files as needed]
```

### File Metadata

Each file has associated metadata:
- **Content**: The actual file content
- **Description**: What this file represents
- **Line count**: Number of lines
- **Required**: Whether it must be in final resolution

This metadata is shown when listing files, making the workspace self-documenting.

### Example Workspace

For the LiveRangeEdit.h conflict:

```
/tmp/conflict_LiveRangeEdit_h_hunk_0/
  base.txt (2 lines)
    Content from merge base - both member variables present

  ours.txt (2 lines)
    Content from our branch (HEAD) - unchanged from base

  theirs.txt (0 lines)
    Content from their branch (upstream) - deleted both variables

  before.txt (10 lines)
    Context before conflict - MUST be first in resolution

  after.txt (10 lines)
    Context after conflict - MUST be last in resolution
```

## Tool Interface

Five simple, composable tools for working with the conflict workspace.

### list_files()

List all available files with descriptions and line counts.

**Parameters**: None

**Returns**: Human-readable list of files with metadata

**Example**:
```
Available files in workspace:

  base.txt (2 lines)
    Content from merge base (common ancestor)

  ours.txt (2 lines)
    Content from our branch (HEAD) - unchanged from base

  theirs.txt (0 lines)
    Content from their branch (upstream) - deleted

  before.txt (10 lines)
    Context before conflict - MUST be first in resolution

  after.txt (10 lines)
    Context after conflict - MUST be last in resolution
```

### read_file(name, start_line=1, end_line=None)

Read content from a file, optionally specifying line range.

**Parameters**:
- name: Filename to read
- start_line: First line to read (default: 1)
- end_line: Last line to read (default: all lines, max 20 unless specified)

**Returns**: File content with line numbers

**Example**:
```
read_file("ours.txt")
→
  1: bool EnableRemat = true;
  2: bool ScannedRemattable = false;
```

**Example with range**:
```
read_file("before.txt", 1, 5)
→
  1: MachineRegisterInfo &MRI;
  2: LiveIntervals &LIS;
  3: VirtRegMap *VRM;
  4: const TargetInstrInfo &TII;
  5: Delegate *const TheDelegate;
```

### write_file(name, content, description="")

Create a new file in the workspace.

**Parameters**:
- name: Filename to create
- content: File content
- description: Optional description of file purpose (shown in list_files)

**Returns**: Confirmation with line count

**Example**:
```
write_file("merged.txt",
           "// Combined logic from both branches\nif (x && y) { ... }",
           "Custom merge combining safety checks from both sides")
→ Created merged.txt (2 lines)
```

### cat_files(input_files, output_file)

Concatenate multiple files into a single output file.

**Parameters**:
- input_files: List of filenames to concatenate (in order)
- output_file: Name of output file to create

**Returns**: Confirmation with total line count

**Example**:
```
cat_files(["before.txt", "theirs.txt", "after.txt"], "resolution.txt")
→ Created resolution.txt (20 lines) from 3 files
```

### submit_resolution(filename)

Submit the final resolution, applying it to the actual conflicted file.

**Parameters**:
- filename: Name of file containing resolution

**Returns**: Success confirmation or validation error

**Validation**:
- File must exist in workspace
- Must start with before.txt content
- Must end with after.txt content

**Example**:
```
submit_resolution("resolution.txt")
→ Resolution applied successfully. File staged with git.
```

## Additional Investigation Tools

The file-based workspace tools work alongside existing investigation tools.

### Git Investigation (Layer 2)

- **git_show_commit(ref, file)**: View commit message and changes
- **git_log(file, max_count)**: View recent commit history
- **show_merge_summary()**: Overview of entire merge operation
- **list_all_conflicts()**: List all conflict hunks in merge

### Codebase Search (Layer 3)

- **grep_codebase(pattern, file_pattern, context)**: Search across repository
- **grep_in_file(file, pattern, context)**: Search within specific file

### Language Server (Layer 4 - Future)

- **query_language_server(file, line, query_type)**: Semantic queries
- **get_type_info(file, symbol)**: Type information
- **check_syntax(file)**: Verify file compiles

These investigation tools help the LLM understand intent before composing the resolution.

## LLM Workflow

The LLM follows a natural workflow using file-based tools.

### Step 1: Understand the Conflict

```
LLM: list_files()

Available files in workspace:

  base.txt (2 lines)
    Content from merge base (common ancestor)

  ours.txt (2 lines)
    Content from our branch (HEAD)

  theirs.txt (0 lines)
    Content from their branch (upstream) - deleted

  before.txt (10 lines)
    Context before conflict - MUST be first in resolution

  after.txt (10 lines)
    Context after conflict - MUST be last in resolution
```

### Step 2: Examine Each Version

```
LLM: read_file("base.txt")
→
  1: bool EnableRemat = true;
  2: bool ScannedRemattable = false;

LLM: read_file("ours.txt")
→
  1: bool EnableRemat = true;
  2: bool ScannedRemattable = false;

LLM: read_file("theirs.txt")
→ (empty - 0 lines)
```

**Analysis**: BASE→OURS shows no change. BASE→THEIRS shows deletion.

### Step 3: Investigate Intent

```
LLM: git_log("LiveRangeEdit.h", 5)
→ Recent commits show: "Refactor: Move rematerialization logic to separate class"

LLM: grep_codebase("EnableRemat")
→ Found in LiveRangeEdit.cpp but checking if still used...

LLM: git_show_commit("upstream/main", "LiveRangeEdit.h")
→ Commit message confirms: "Extracted rematerialization to RematerializationAnalyzer class"
```

### Step 4: Compose Resolution

For simple case (accept deletion):
```
LLM: cat_files(["before.txt", "after.txt"], "resolution.txt")
→ Created resolution.txt (20 lines) from 2 files
```

For complex case (custom merge):
```
LLM: write_file("merged.txt",
                "// Keeping partial functionality\nbool EnableRemat = true;",
                "Partial merge - keep EnableRemat but not ScannedRemattable")

LLM: cat_files(["before.txt", "merged.txt", "after.txt"], "resolution.txt")
→ Created resolution.txt (21 lines) from 3 files
```

### Step 5: Submit Resolution

```
LLM: submit_resolution("resolution.txt")
→ Resolution applied successfully. File staged with git.
```

## Prompt Engineering

The LLM prompt guides the file-based workflow.

### Initial Prompt Template

```
You are resolving a merge conflict in {file_path}.

CONFLICT CONTEXT:
  Commit pair: ({i1}, {i2})
  Our commit: {commit_ours_message}
  Their commit: {commit_theirs_message}

WORKSPACE:
A workspace has been created with files representing this conflict.
Use list_files() to see available files.

PROCESS:
1. List files to see what's available
2. Read base.txt, ours.txt, theirs.txt to understand changes
3. Investigate using git_log, grep_codebase if needed
4. Create your resolution by composing files
5. Submit your resolution

RESOLUTION REQUIREMENTS:
- Must start with before.txt content
- Must end with after.txt content
- Middle section is your choice of base/ours/theirs/custom

COMMON PATTERNS:

Accept theirs (deletion):
  cat_files(["before.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Accept theirs (changed content):
  cat_files(["before.txt", "theirs.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Accept ours:
  cat_files(["before.txt", "ours.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Accept both (if compatible):
  cat_files(["before.txt", "ours.txt", "theirs.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Custom merge:
  write_file("merged.txt", "your custom content", "description")
  cat_files(["before.txt", "merged.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

AVAILABLE TOOLS:
File operations: list_files, read_file, write_file, cat_files, submit_resolution
Investigation: git_log, git_show_commit, grep_codebase, grep_in_file
Context: show_merge_summary, list_all_conflicts

Begin by listing files to see the conflict.
```

### Chain-of-Thought Guidance

```
Think step-by-step:

1. EXAMINE FILES
   - What's in base.txt, ours.txt, theirs.txt?
   - What changed: BASE→OURS? BASE→THEIRS?
   - Are changes related or independent?

2. UNDERSTAND INTENT
   - Why did we make our changes?
   - Why did they make their changes?
   - Check git_log and commit messages

3. INVESTIGATE IF NEEDED
   - Is deleted code used elsewhere? (grep_codebase)
   - What's the broader context? (read_file on before/after)
   - Are there related changes? (git_show_commit)

4. COMPOSE RESOLUTION
   - Choose: ours, theirs, both, or custom?
   - Create intermediate files if needed
   - Concatenate in correct order: before + content + after

5. SUBMIT
   - Validate resolution makes sense
   - Submit with confidence score and reasoning
```

### Few-Shot Examples

Examples showing the file-based workflow:

**Example 1: Simple Deletion**
```
Conflict: Upstream deleted member variables

list_files() shows theirs.txt is empty (0 lines)

read_file("base.txt") → two member variables
read_file("ours.txt") → same two variables (unchanged)
read_file("theirs.txt") → empty (deleted)

Investigation:
  git_log shows "Refactored to separate class"
  grep_codebase confirms not used elsewhere

Resolution:
  cat_files(["before.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Reasoning: Safe to accept deletion as part of refactoring
```

**Example 2: Logic Merge**
```
Conflict: Both sides added different safety checks

read_file("base.txt") → if user.active: login()
read_file("ours.txt") → if user.active and not blocked: login()
read_file("theirs.txt") → if user.active and not rate_limited: login()

Analysis: Both added independent safety checks

Resolution:
  write_file("merged.txt",
             "if user.active and not blocked and not rate_limited: login()",
             "Combined both safety checks")
  cat_files(["before.txt", "merged.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Reasoning: Both checks are needed for security
```

**Example 3: Uncertain Case**
```
Conflict: Complex algorithm change

read_file("theirs.txt") shows significant algorithm rewrite

Investigation:
  git_show_commit → "Optimize for performance"
  grep_codebase → algorithm used in MOS-specific code

Analysis: Cannot determine if optimization is compatible with MOS target

Resolution:
  write_file("analysis.txt",
             "THEIRS rewrote algorithm but unclear if MOS-compatible",
             "Analysis notes - flagging for human review")

  cat_files(["before.txt", "ours.txt", "after.txt"], "resolution.txt")
  submit_resolution("resolution.txt")

Reasoning: Keeping ours (safe), but flagging for human review
Confidence: 0.6
Needs human review: true
```

## Resolution Decision Format

The LLM outputs a decision in YAML format (in markdown code block).

### Decision Schema

```yaml
action: accept_ours | accept_theirs | accept_both | custom
reasoning: |
  Clear explanation of the decision.
  Multiple lines allowed.
confidence: 0.85
needs_human_review: false
files_used:
  - base.txt
  - ours.txt
  - theirs.txt
  - resolution.txt
intermediate_files:
  - analysis.txt: "Notes on why this was tricky"
```

### Why YAML in Markdown

LLMs handle YAML better than JSON:
- Indentation-based (like Python)
- Multi-line strings are natural with `|`
- Fewer syntax errors
- More readable in prompts

### Parsing Strategy

Extract YAML block from LLM response:

```python
import re
import yaml

def extract_decision(llm_response: str) -> dict:
    """Extract YAML decision from LLM response."""
    match = re.search(r'```yaml\n(.*?)\n```', llm_response, re.DOTALL)
    if not match:
        raise ValueError("No YAML decision found in response")

    yaml_text = match.group(1)
    return yaml.safe_load(yaml_text)
```

## Implementation

### Workspace Creation

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class FileMetadata:
    """Metadata for a workspace file."""
    content: str
    description: str
    required_in_resolution: bool = False

    @property
    def line_count(self) -> int:
        return len(self.content.splitlines()) if self.content else 0

class ConflictWorkspace:
    """Workspace containing files for one conflict hunk."""

    def __init__(self, conflict_hunk: ConflictHunk, workspace_id: str):
        """Initialize workspace from conflict hunk.

        Args:
            conflict_hunk: Parsed conflict data
            workspace_id: Unique identifier for workspace directory
        """
        self.workdir = Path("/tmp") / f"conflict_{workspace_id}"
        self.workdir.mkdir(parents=True, exist_ok=True)

        # Create file metadata
        self.files = {
            "base.txt": FileMetadata(
                content=conflict_hunk.base_content,
                description="Content from merge base (common ancestor)",
                required_in_resolution=False,
            ),
            "ours.txt": FileMetadata(
                content=conflict_hunk.ours_content,
                description=f"Content from our branch ({conflict_hunk.ours_ref})",
                required_in_resolution=False,
            ),
            "theirs.txt": FileMetadata(
                content=conflict_hunk.theirs_content,
                description=f"Content from their branch ({conflict_hunk.theirs_ref})",
                required_in_resolution=False,
            ),
            "before.txt": FileMetadata(
                content="\n".join(conflict_hunk.context_before),
                description="Context before conflict - MUST be first in resolution",
                required_in_resolution=True,
            ),
            "after.txt": FileMetadata(
                content="\n".join(conflict_hunk.context_after),
                description="Context after conflict - MUST be last in resolution",
                required_in_resolution=True,
            ),
        }

        # Write all initial files
        for filename, meta in self.files.items():
            self._write_to_disk(filename, meta.content)

    def _write_to_disk(self, filename: str, content: str):
        """Write file to workspace directory."""
        (self.workdir / filename).write_text(content)
```

### Tool Implementation

```python
class WorkspaceTools:
    """Tools for working with conflict workspace."""

    def __init__(self, workspace: ConflictWorkspace):
        self.workspace = workspace

    def list_files(self) -> str:
        """List all files with descriptions."""
        lines = ["Available files in workspace:\n"]

        for filename, meta in self.workspace.files.items():
            lines.append(f"  {filename} ({meta.line_count} lines)")
            lines.append(f"    {meta.description}\n")

        return "\n".join(lines)

    def read_file(self, name: str, start_line: int = 1,
                  end_line: int | None = None) -> str:
        """Read file content with line numbers."""
        if name not in self.workspace.files:
            return f"Error: File '{name}' not found. Use list_files() to see available files."

        content = self.workspace.files[name].content
        lines = content.splitlines()

        # Default to showing first 20 lines if no end specified
        if end_line is None:
            end_line = min(len(lines), 20)

        # Extract range (1-indexed)
        selected_lines = lines[start_line - 1:end_line]

        # Format with line numbers
        output = []
        for i, line in enumerate(selected_lines, start=start_line):
            output.append(f"  {i}: {line}")

        return "\n".join(output)

    def write_file(self, name: str, content: str,
                   description: str = "") -> str:
        """Create new file in workspace."""
        self.workspace.files[name] = FileMetadata(
            content=content,
            description=description or "User-created file",
            required_in_resolution=False,
        )
        self.workspace._write_to_disk(name, content)

        line_count = len(content.splitlines())
        return f"Created {name} ({line_count} lines)"

    def cat_files(self, input_files: list[str], output_file: str) -> str:
        """Concatenate files into output."""
        # Validate all input files exist
        for filename in input_files:
            if filename not in self.workspace.files:
                return f"Error: File '{filename}' not found"

        # Concatenate
        parts = [self.workspace.files[f].content for f in input_files]
        concatenated = "\n".join(parts)

        # Create output file
        self.workspace.files[output_file] = FileMetadata(
            content=concatenated,
            description=f"Concatenation of {len(input_files)} files",
            required_in_resolution=False,
        )
        self.workspace._write_to_disk(output_file, concatenated)

        line_count = len(concatenated.splitlines())
        return f"Created {output_file} ({line_count} lines) from {len(input_files)} files"

    def submit_resolution(self, filename: str) -> str:
        """Submit resolution file."""
        if filename not in self.workspace.files:
            return f"Error: File '{filename}' not found"

        resolution = self.workspace.files[filename].content
        before = self.workspace.files["before.txt"].content
        after = self.workspace.files["after.txt"].content

        # Validate structure
        if not resolution.startswith(before):
            return "Error: Resolution must start with before.txt content"

        if not resolution.endswith(after):
            return "Error: Resolution must end with after.txt content"

        # Apply resolution (implementation in resolve_conflicts node)
        return f"Resolution accepted from {filename}. Ready to apply."
```

### LangGraph Integration

The file-based tools integrate into the resolution subgraph:

```python
def create_resolution_subgraph():
    """Create resolution subgraph with file-based tools."""

    # Initialize workspace (done in present_conflict node)
    def present_conflict(state):
        workspace = ConflictWorkspace(state.current_hunk, workspace_id=...)
        tools = WorkspaceTools(workspace)

        # Add initial message with prompt
        prompt = create_file_based_prompt(workspace, state)
        state.messages = [HumanMessage(content=prompt)]
        state.workspace = workspace
        state.tools = tools
        return state

    # LLM decides (with file tools)
    def llm_decide(state):
        llm = ChatOpenAI(...).bind_tools([
            state.tools.list_files,
            state.tools.read_file,
            state.tools.write_file,
            state.tools.cat_files,
            state.tools.submit_resolution,
            # Plus investigation tools
            git_log_tool,
            grep_codebase_tool,
            ...
        ])

        response = llm.invoke(state.messages)
        state.messages.append(response)
        return state

    # Extract resolution (when submit_resolution called)
    def extract_resolution(state):
        # Find submit_resolution tool call
        last_msg = state.messages[-1]
        for tool_call in last_msg.tool_calls:
            if tool_call["name"] == "submit_resolution":
                filename = tool_call["args"]["filename"]
                resolution_content = state.workspace.files[filename].content

                # Extract YAML decision from messages
                decision = extract_decision_from_messages(state.messages)

                state.resolution = Resolution(
                    content=resolution_content,
                    decision=decision,
                )
                return state
```

## Benefits

### Compared to "Regenerate Entire File" Approach

**Cost**:
- Old: ~10,000 tokens per large file
- New: ~200-500 tokens per conflict (20-50x cheaper)

**Accuracy**:
- Old: LLM can make typos anywhere in 8,896 lines
- New: LLM only composes small sections

**Speed**:
- Old: 30+ seconds to regenerate large file
- New: 3-5 seconds per conflict resolution

**Observability**:
- Old: Black box - don't know why LLM decided something
- New: Full workspace with intermediate files shows thought process

**Debuggability**:
- Old: Must re-run to see what happened
- New: Workspace files persist in /tmp for inspection

### Compared to Abstract Tool Approach

**Simplicity**:
- Old: Complex layered tools (view_conflict, resolve_conflict, view_more_context...)
- New: Five simple file operations (list, read, write, cat, submit)

**Flexibility**:
- Old: Fixed resolution actions (ours/theirs/both/custom)
- New: Arbitrary composition via file operations

**LLM-Friendly**:
- Old: Abstract conflict IDs and resolution parameters
- New: Concrete files with clear names and descriptions

**Composability**:
- Old: One-shot resolution via tool call
- New: Build resolution incrementally, create intermediate artifacts

## Design Principles

### 1. Files as Primary Interface

Everything is a file:
- Conflict sections (base.txt, ours.txt, theirs.txt)
- Context (before.txt, after.txt)
- Intermediate work (analysis.txt, merged.txt)
- Final resolution (resolution.txt)

Files are concrete, debuggable, and familiar to LLMs.

### 2. Composition via Concatenation

Resolution is built by concatenating files:
- Simple cases: `cat before.txt theirs.txt after.txt`
- Complex cases: Create intermediate files, then concatenate

This is the Unix way - simple tools, powerful combinations.

### 3. Self-Documenting Workspace

Every file has a description shown by list_files():
- LLM always knows what each file represents
- Required files are clearly marked
- User-created files get descriptions too

No need to remember abstract IDs or parameters.

### 4. Progressive Enhancement

Core tools (list, read, write, cat, submit) work standalone.
Investigation tools (git, grep) add capability.
Future tools (LSP) add semantic understanding.

System works in minimal environment, improves with more tools.

### 5. Explicit Intermediate Artifacts

LLM can create analysis files, notes, partial merges:
- Thought process is visible
- Debugging is easier
- Can inspect workspace after completion

Transparency by design.

### 6. Validation at Boundaries

Tools validate at submit time:
- Resolution must include required files
- Structure is checked (before → content → after)
- Clear error messages guide LLM

But LLM has freedom to compose however it wants.

## Future Enhancements

### Workspace Templates

Pre-populate workspace with common patterns:

```
/tmp/conflict_xyz/
  base.txt, ours.txt, theirs.txt, before.txt, after.txt

  templates/
    accept_ours.txt - Pre-concatenated version accepting ours
    accept_theirs.txt - Pre-concatenated version accepting theirs
    accept_both.txt - Pre-concatenated version with both
```

LLM can read templates as starting points.

### Diff Visualization

Add tool to show diffs between files:

```
diff_files("base.txt", "theirs.txt")
→
  1: bool EnableRemat = true;
  2: bool ScannedRemattable = false;

  1: (deleted)
  2: (deleted)
```

### Semantic Annotations

Enrich files with semantic comments from commit analysis:

```
# THEIRS: Deleted as part of refactoring to RematerializationAnalyzer
# See commit abc123: "Extract rematerialization logic"
<<<<<<< HEAD
...
```

### Multi-File Conflicts

For conflicts spanning multiple related files, create cross-file workspace:

```
/tmp/conflict_xyz/
  file1/
    base.txt, ours.txt, theirs.txt, before.txt, after.txt
  file2/
    base.txt, ours.txt, theirs.txt, before.txt, after.txt

  cross_file_analysis.txt
```

### Pattern Learning

Track which composition patterns worked:
- File combinations that passed tests
- Successful custom merges
- Common investigation sequences

Use to suggest patterns in future conflicts.

## References

- Unix philosophy: Small tools, composition, files as interface
- git-imerge: Incremental merge subdivision
- LangChain tool calling: Agent with tools pattern
- Gmerge (Microsoft 2022): Research on merge conflict presentation
- llvm-mos project: Real-world merge examples
