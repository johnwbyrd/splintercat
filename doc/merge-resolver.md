# Merge Resolver Design - Tool-Based LLM Conflict Resolution

## Problem Statement

Traditional LLM approaches to merge conflict resolution fail because they require the LLM to regenerate entire files. This is:

- **Expensive**: Large files cost many tokens to regenerate
- **Error-prone**: LLMs make typos, miss details, or change unrelated code
- **Slow**: Generating 8,000+ lines takes significant time
- **Wasteful**: Most of the file is unchanged, only small conflict sections need resolution

### Real-World Example

File: `llvm/tools/llvm-readobj/ELFDumper.cpp`
- Size: 8,896 lines
- Conflicts: 1 conflict at line 1139 (80 lines of enum entries)
- Problem: LLM must regenerate 8,896 lines perfectly to resolve an 80-line conflict

## Solution: Tool-Based Resolution

Instead of treating the LLM as a text generator, treat it as an **analyst with tools**.

### Key Insight

LLMs should:
1. **Observe** the conflict with context
2. **Investigate** using tools to understand intent
3. **Reason** about the best resolution
4. **Question** when uncertain
5. **Execute** precise edits using tools
6. **Explain** their reasoning

LLMs work best with chunks of text and context, not regenerating entire files.

## Architecture: Layered Tools

### Layer 1: Core Conflict Tools (MVP)

Minimal tools to view and resolve conflicts.

**Tools:**
```
view_conflict(file, conflict_num, context_lines=10)
  Shows conflict with surrounding context (default 10 lines before/after)

view_more_context(file, conflict_num, before=N, after=N)
  Expands context when LLM needs more information

resolve_conflict(file, conflict_num, choice, custom_text=None)
  Resolves conflict with choice: "ours" | "theirs" | "both" | "custom"
```

**Example Output:**
```
File: llvm/include/llvm/CodeGen/LiveRangeEdit.h
Conflict 1 of 2 (at logical position in class definition):

  70:   MachineRegisterInfo &MRI;
  71:   LiveIntervals &LIS;
  72:   VirtRegMap *VRM;
  73:   const TargetInstrInfo &TII;
  74:   Delegate *const TheDelegate;
  75:
  76:   const unsigned FirstNew;
  77:
  78: <<<<<<< HEAD
  79:   bool EnableRemat = true;
  80:   bool ScannedRemattable = false;
  81:
  82: =======
  83: >>>>>>> heaven/main
  84:   /// DeadRemats - The saved instructions which have already been dead
  85:   SmallVector<MachineInstr *, 32> DeadRemats;
```

### Layer 2: Basic Investigation Tools

Understand why changes were made and see the bigger picture.

**Tools:**
```
git_show_commit(ref, file)
  Shows commit message and changes for why this file was modified

git_log(file, max_count=10)
  Shows recent history of file changes

show_merge_summary()
  Overview: "Merging X into Y, N files with M total conflicts"

list_all_conflicts()
  Shows all conflicts across all files in this merge
```

**Use Case:**
LLM sees a large deletion and wonders why. Calls `git_show_commit("heaven/main", "ELFDumper.cpp")` and learns: "Cleanup: removed unused architecture types". This context helps decide whether to keep or remove code.

### Layer 3: Codebase Search Tools

Search and understand the codebase to make informed decisions.

**Tools:**
```
grep_codebase(pattern, file_pattern=None)
  Search for pattern across codebase
  Example: grep_codebase("EM_MOS") finds MOS-specific references

grep_in_file(file, pattern)
  Search within a specific file
```

**Use Case:**
LLM sees `EnableRemat` being deleted. Calls `grep_codebase("EnableRemat")` to find if it's used elsewhere. If not found, safely accepts deletion. If found, investigates further.

### Layer 4: Language Server Integration (Future)

Deep semantic understanding when language server (like clangd) is available.

**Tools:**
```
query_language_server(file, line, query_type)
  query_type: "definition" | "references" | "hover" | "signature"

get_type_info(file, symbol)
  Get type information for a symbol

get_function_signature(file, function_name)
  Get function signature and documentation

check_syntax(file)
  Verify file compiles after resolution
```

**Use Case:**
LLM is unsure if deleted method is still needed. Calls `query_language_server(file, method_name, "references")` to see all callers. If no callers exist, safe to delete.

### Layer 5: Extended Context (Future)

Additional context from external sources when available.

**Tools:**
```
search_documentation(query)
  Search external documentation (via MCP or web)

fetch_url(url)
  Fetch external information

ask_human(question)
  Ask human for clarification (interactive mode only)
```

**Use Case:**
LLM encounters unfamiliar API change. Calls `search_documentation("LLVM LiveInterval API changes")` to understand upstream refactoring.

## Workflow Example: ELFDumper.cpp

### Scenario
- File: 8,896 lines
- Conflict: 1 conflict in enum array (80 lines)
- Type: Upstream deleted old CPU architecture entries

### LLM Resolution Process

**Step 1: Observe**
```
LLM calls: view_conflict("ELFDumper.cpp", 1)

Response shows:
  1138: const EnumEntry<unsigned> ElfMachineType[] = {
  1139: <<<<<<< HEAD
        ENUM_ENT(EM_NONE, "None"),
        ENUM_ENT(EM_M32, "WE32100"),
        ... (80 more ENUM_ENT lines)
  1220: =======
  1221: >>>>>>> heaven/main
  1222:   ENUM_ENT(EM_OPENRISC, "OpenRISC 32-bit embedded processor"),
```

**Step 2: Understand Context**
```
LLM calls: show_merge_summary()
Response: "Merging LLVM upstream (heaven/main) into llvm-mos fork. 7 files, 12 conflicts."

LLM thinks: "This is llvm-mos, a MOS 65xx fork of LLVM. MOS-specific code is important."
```

**Step 3: Investigate**
```
LLM calls: git_show_commit("heaven/main", "ELFDumper.cpp")
Response: "Commit abc123: Remove unused architecture types - cleanup PR"

LLM calls: grep_codebase("EM_MOS")
Response: "Found in 15 files - this is a core part of llvm-mos"

LLM calls: view_more_context("ELFDumper.cpp", 1, before=0, after=50)
Response shows: None of the deleted entries are EM_MOS-related
```

**Step 4: Reason**
```
LLM reasoning:
"Upstream cleaned up unused architectures. The deleted entries are all
standard architectures (SPARC, M32, etc.). The MOS-specific entries are
not in this conflict block. Safe to accept upstream's cleanup."
```

**Step 5: Execute**
```
LLM calls: resolve_conflict("ELFDumper.cpp", 1, choice="theirs")

LLM explains: "Accepted upstream deletion. General architecture cleanup,
no MOS-specific entries affected. Verified EM_MOS entries are elsewhere."
```

## Workflow Example: LiveRangeEdit.h

### Scenario
- File: 459 lines
- Conflicts: 2 conflicts (lines 78 and 177)
- Type: Deleted member variables and method

### LLM Resolution Process

**Step 1: Observe Both Conflicts**
```
LLM calls: view_conflict("LiveRangeEdit.h", 1)
Shows: EnableRemat and ScannedRemattable member variables deleted

LLM calls: view_conflict("LiveRangeEdit.h", 2)
Shows: Some method deleted
```

**Step 2: Investigate Relationship**
```
LLM calls: grep_in_file("LiveRangeEdit.h", "EnableRemat")
Response: "Only appears in conflict block"

LLM calls: grep_codebase("EnableRemat")
Response: "Found in LiveRangeEdit.cpp - the implementation file"

LLM calls: git_log("LiveRangeEdit.h", max_count=5)
Response shows: "Refactoring: moved rematerialization logic to separate class"
```

**Step 3: Reason**
```
LLM reasoning:
"Both conflicts are part of same refactoring. Upstream moved
rematerialization logic elsewhere. Related member variables and
methods should be deleted together. This is a coordinated change."
```

**Step 4: Execute**
```
LLM calls: resolve_conflict("LiveRangeEdit.h", 1, choice="theirs")
LLM calls: resolve_conflict("LiveRangeEdit.h", 2, choice="theirs")

LLM explains: "Accepted both deletions. Part of upstream refactoring
that moved rematerialization logic to separate class. Coordinated change."
```

## Design Principles

### 1. Context-First

Every tool returns human-readable text with natural context, not just data.

**Good:**
```
Function foo() at line 120:
  void foo() {
    int x = 5;  // <-- Definition
    return x;
  }
```

**Bad:**
```
{"function": "foo", "line": 120, "type": "void"}
```

### 2. Progressive Enhancement

Tools build on each other. Core tools work standalone, advanced tools add capability.

- Layer 1 works without anything else
- Layer 2 adds git understanding
- Layer 3 adds codebase search
- Layer 4 adds LSP (when available)
- Layer 5 adds external context (when available)

### 3. Graceful Degradation

If advanced tools unavailable, basic tools still work.

- No clangd? Use grep instead
- No MCP? Use local tools
- No human available? Log questions and proceed

### 4. LLM-Friendly

Design for how LLMs actually think:
- Show context (10 lines around conflicts)
- Natural language descriptions
- Simple choices: ours/theirs/both
- Allow questions and exploration

### 5. Observable

All LLM actions are logged:
- What tools it used
- What it discovered
- How it reasoned
- What it decided
- Why it decided that way

## Implementation Phases

### Phase 1: Core Tools (MVP)
- Implement Layer 1 (view_conflict, resolve_conflict)
- Update main.py to use tool-based resolver
- Test with real conflicts

### Phase 2: Investigation
- Add Layer 2 (git_show_commit, git_log, merge summary)
- Test with conflicts requiring context

### Phase 3: Codebase Search
- Add Layer 3 (grep_codebase, find_definition)
- Test with refactoring conflicts

### Phase 4: Language Server
- Add Layer 4 (LSP integration)
- Requires clangd or similar LSP server running
- Optional, graceful degradation

### Phase 5: Extended Context
- Add Layer 5 (MCP integration, human questions)
- Build on MCP tools if available

## Configuration

```yaml
resolver:
  # Context size for viewing conflicts
  default_context_lines: 10
  max_context_lines: 100

  # Tool availability
  enable_git_tools: true
  enable_grep_tools: true
  enable_language_server: false  # Requires LSP setup

  # Interactive mode
  allow_human_questions: false  # Set true for interactive

  # Logging
  log_tool_usage: true
  log_llm_reasoning: true
```

## Benefits

### Compared to "Regenerate Entire File" Approach

**Cost:**
- Old: ~10,000 tokens per large file
- New: ~500 tokens per conflict (20x cheaper)

**Accuracy:**
- Old: LLM can make typos anywhere in 8,896 lines
- New: LLM only edits specific conflict blocks

**Speed:**
- Old: 30+ seconds to regenerate large file
- New: 3-5 seconds per conflict resolution

**Observability:**
- Old: Black box - don't know why LLM decided something
- New: Full log of investigation and reasoning

**Extensibility:**
- Old: Hard to add new capabilities
- New: Just add new tools to registry

## Future Enhancements

### Smart Conflict Detection
- Detect conflict patterns (enum lists, import statements, etc.)
- Suggest automatic resolution strategies
- "This looks like a list merge - want me to merge both sides?"

### Learning from History
- Track which resolutions worked (passed tests)
- Learn patterns: "MOS-specific code should usually be kept"
- Suggest resolutions based on similar past conflicts

### Parallel Resolution
- Resolve independent conflicts in parallel
- Use multiple LLM calls concurrently for speed

### Test-Driven Resolution
- Run tests after each resolution
- Automatically revert if tests fail
- Iteratively refine until tests pass

## References

- Inspiration: merde.ai - LLM-based merge tool with clipboard/editor metaphor
- LangChain tool/function calling documentation
- LLVM merge examples from llvm-mos project
