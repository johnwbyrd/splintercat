# Check-Runner Tool Design

## Problem Statement

The Resolver LLM currently has no way to validate its work during conflict resolution. It must:
1. Resolve all conflicts in a pair
2. Submit resolutions
3. Hope the workflow eventually runs checks

If the check fails hours later after resolving 50 more conflicts, the LLM has no context about what it did wrong.

## Proposal: Add `run_check` Tool to Resolver

Give the Resolver LLM a tool to run validation checks synchronously during conflict resolution. This allows immediate feedback:

```python
# LLM resolves a critical file
write_file('lib/IR/Globals.cpp', resolved_content)

# LLM is uncertain, wants to validate immediately
result = run_check('quick')  # Blocks until check completes

if 'FAILED' in result:
    # Fix and retry before moving on
    write_file('lib/IR/Globals.cpp', fixed_content)
    result = run_check('quick')

# Now confident, submit
submit_resolution('lib/IR/Globals.cpp')
```

## Tool Interface

### Function Signature
```python
def run_check(
    ctx: RunContext[Workspace],
    check_level: str,
) -> str:
    """Run a validation check and return results synchronously.

    Blocks until check completes. Use for immediate validation
    of recent changes. Full log saved to timestamped file.

    Args:
        check_level: Name of check from config.check.commands
                     Common: 'quick' (syntax/fast compile)
                             'normal' (full build)
                             'full' (build + test suite)
                     Or any custom check name from config

    Returns:
        Concise summary of check result (success or failure with excerpt)

    Raises:
        ModelRetry: If check_level not defined in config
    """
```

### Tool Behavior

**Synchronous from LLM perspective**:
- LLM calls tool
- Tool execution blocks (runs check command)
- Tool returns result
- LLM sees output and continues

**From workflow perspective**:
- Still inside `resolve_workspace()` agent execution
- Workflow node (ResolveConflicts) is already blocked waiting for agent
- Tool just adds time to agent execution

**No workflow routing**:
- Doesn't change workflow state
- Doesn't route to different nodes
- Pure information gathering for Resolver

## Check Levels (User-Defined)

Check levels come from `config.check.commands`:

```yaml
config:
  check:
    output_dir: .splintercat/logs
    timeout: 3600
    commands:
      quick: "ninja -C build lib/IR lib/CodeGen"  # Fast subset
      normal: "ninja -C build"                    # Full build
      full: "ninja -C build && ninja test"        # Build + tests
      syntax: "find . -name '*.cpp' -exec clang++ -fsyntax-only {} \;"
      custom_ir: "ninja -C build lib/IR && ninja test-ir"
```

**User controls**:
- Which checks exist
- What commands they run
- What "quick" vs "normal" vs "full" mean for their project

**Resolver uses them**:
- Calls `run_check('quick')` for fast validation
- Calls `run_check('normal')` for comprehensive build
- Calls `run_check('custom_ir')` after IR-specific changes

## Output Format

### On Success
```
Check 'normal' PASSED

Completed in 8.3 seconds
Log: /path/to/.splintercat/logs/normal-20251016-211530.log
```

Concise - LLM doesn't need details when things work.

### On Failure
```
Check 'normal' FAILED
Returncode: 1
Completed in 12.1 seconds

Last 30 lines of output:
[21/2734] Building CXX object lib/IR/CMakeFiles/LLVMCore.dir/Globals.cpp.o
FAILED: lib/IR/CMakeFiles/LLVMCore.dir/Globals.cpp.o
/home/user/llvm/lib/IR/Globals.cpp:423:10: error: duplicate case value 'AddrSpaceCast'
  423 |     case Instruction::AddrSpaceCast:
      |          ^
/home/user/llvm/lib/IR/Globals.cpp:418:10: note: previous case defined here
  418 |     case Instruction::AddrSpaceCast:
      |          ^
1 error generated.
ninja: build stopped: subcommand failed.

Full log: /path/to/.splintercat/logs/normal-20251016-211530.log
```

Shows enough context to understand the error, but not thousands of lines.

## When Resolver Should Use This Tool

### Good Use Cases

**1. After Resolving High-Risk Files**
```python
# Just resolved critical IR file
write_file('lib/IR/Globals.cpp', resolution)

# Validate immediately before moving on
result = run_check('quick')
if 'PASSED' in result:
    submit_resolution('lib/IR/Globals.cpp')
```

**2. Uncertain About Resolution**
```python
# Complex merge with multiple conflicting changes
write_file('lib/CodeGen/SelectionDAG.cpp', merged_content)

# Not confident, check it
result = run_check('normal')
if 'FAILED' in result:
    # Analyze error, fix, retry
    ...
```

**3. Before Batch Gets Large**
```python
# Just resolved 5 conflicts in same module
submit_resolution('file5.cpp')

# Check now before resolving 10 more
result = run_check('normal')
# If failed, better to know now than after 15 total conflicts
```

### When NOT to Use

**1. Low-Risk Files**
```python
# Just resolved documentation
write_file('docs/UserGuide.md', resolved)
# No need to run build, just submit
submit_resolution('docs/UserGuide.md')
```

**2. Too Frequently**
```python
# Don't do this:
for file in conflict_files:
    write_file(file, resolved)
    run_check('normal')  # Wasteful - check after all files
    submit_resolution(file)

# Instead:
for file in conflict_files:
    write_file(file, resolved)
    submit_resolution(file)
run_check('normal')  # Once after batch
```

**3. After Trivial Changes**
```python
# Fixed typo in comment
write_file('main.cpp', fixed_comment)
# No need to rebuild entire project
submit_resolution('main.cpp')
```

## Relationship to Other Checks

There are **three types of checks** in splintercat:

### 1. Resolver Tool Check (This Document)
- **Triggered by**: Resolver LLM calling `run_check()` tool
- **Purpose**: Immediate validation during conflict resolution
- **Scope**: Single conflict pair (i1, i2) resolution
- **Blocking**: Yes - tool call blocks until check completes
- **Example**: "I just fixed Globals.cpp, let me verify it compiles"

### 2. Coordinator Workflow Check
- **Triggered by**: Coordinator LLM deciding to validate batch
- **Purpose**: Validate batch of resolutions before continuing
- **Scope**: Multiple conflict pairs (5-20 conflicts)
- **Blocking**: Yes - workflow waits for check to complete
- **Example**: "Resolved 10 conflicts in IR module, validate before continuing"

### 3. Final Validation Check
- **Triggered by**: Workflow before Finalize node
- **Purpose**: Comprehensive validation before creating merge commit
- **Scope**: Entire merge (all conflicts resolved)
- **Blocking**: Yes - must pass before finalize
- **Example**: "All conflicts done, run full test suite before committing"

### How They Interact

```
ResolveConflicts node:
  ├─> Resolver agent runs
  │     ├─> Resolves file 1
  │     ├─> run_check('quick')  ← Resolver tool check
  │     ├─> Resolves file 2
  │     └─> submit_resolution(...)
  │
  ├─> Return to Coordinator
  │
  └─> Coordinator decides: run_checks(['normal'])  ← Coordinator check
        ↓
      Check node runs
        ↓
      Back to Coordinator
        ↓
      More conflicts or Finalize
        ↓
      Final check before commit  ← Final validation
```

All three use the same underlying `CheckRunner` class, but serve different purposes in the workflow.

## Implementation Notes

### Reuse Existing CheckRunner

Don't create new check execution code. Reuse existing:

```python
def run_check(
    ctx: RunContext[Workspace],
    check_level: str,
) -> str:
    # Get command from config
    cmd = ctx.deps.config.check.commands.get(check_level)
    if not cmd:
        available = ', '.join(ctx.deps.config.check.commands.keys())
        raise ModelRetry(
            f"Check level '{check_level}' not defined. "
            f"Available: {available}"
        )

    # Use existing CheckRunner (same as workflow checks)
    from splintercat.runner.check import CheckRunner
    runner = CheckRunner(
        workdir=ctx.deps.workdir,
        output_dir=ctx.deps.config.check.output_dir
    )

    result = runner.run(
        check_name=check_level,
        command=cmd,
        timeout=ctx.deps.config.check.timeout
    )

    # Format output for LLM
    if result.success:
        return f"Check '{check_level}' PASSED\n\nLog: {result.log_file}"
    else:
        # Read last N lines of log
        log_tail = result.log_file.read_text().split('\n')[-30:]
        errors = '\n'.join(log_tail)

        return f"""Check '{check_level}' FAILED
Returncode: {result.returncode}

Last 30 lines:
{errors}

Full log: {result.log_file}
"""
```

### Add to Workspace Tools

```python
# In tools/__init__.py
workspace_tools = [
    run_command,
    list_allowed_commands,
    read_file,
    write_file,
    concatenate_to_file,
    submit_resolution,
    run_check,  # NEW
]
```

### Update Resolver Prompt

```yaml
# In defaults/prompts.yaml
resolver:
  system: |
    ...existing tools...

    7. run_check(check_level) - Run validation check
       Levels defined in config (typically: quick, normal, full)

       Use when:
       - After resolving high-risk files (IR, CodeGen, core APIs)
       - Uncertain about resolution correctness
       - Before batch gets large (e.g., after 5 conflicts in same module)

       Blocks until check completes. Returns PASSED or FAILED with error excerpt.

       Example:
         write_file('lib/IR/Globals.cpp', resolved_content)
         result = run_check('quick')
         if 'PASSED' in result:
             submit_resolution('lib/IR/Globals.cpp')
         else:
             # Analyze error in result, fix issue, retry
```

## Performance Considerations

### Check Duration
- **quick**: 10-30 seconds (syntax check or small subset)
- **normal**: 1-5 minutes (full build)
- **full**: 5-30 minutes (build + test suite)

Resolver should choose appropriate level for situation:
- Quick validation: use 'quick'
- Comprehensive: use 'normal'
- Critical code path: use 'full'

### Token Cost
Check output consumes tokens. Keep output concise:
- Success: ~50 tokens
- Failure: ~300-500 tokens (last 30 lines of log)

Full log saved to file (not sent to LLM).

### Check Frequency
Running checks too often wastes time and money:
- Bad: Check after every file (10 conflicts = 10 checks = 10-50 minutes)
- Good: Check after batch (10 conflicts = 1 check = 1-5 minutes)

Coordinator can enforce minimum intervals if Resolver checks too aggressively.

## Example Usage Patterns

### Pattern 1: Critical File Validation
```python
# Resolver working on high-risk IR file

read_file('lib/IR/Globals.cpp')
run_command('git', ['show', ':1:lib/IR/Globals.cpp'])  # base
run_command('git', ['show', ':2:lib/IR/Globals.cpp'])  # ours
run_command('git', ['show', ':3:lib/IR/Globals.cpp'])  # theirs

# Analyze and merge
write_file('lib/IR/Globals.cpp', resolution)

# Critical file - validate immediately
result = run_check('quick')

if 'FAILED' in result:
    # Error shows duplicate case statement
    # Fix the issue
    write_file('lib/IR/Globals.cpp', fixed_resolution)
    result = run_check('quick')

# Passes now
submit_resolution('lib/IR/Globals.cpp')
```

### Pattern 2: Batch Validation
```python
# Resolver working on multiple files in same module

files = ['IRBuilder.cpp', 'Constants.cpp', 'Globals.cpp']

for file in files:
    read_file(file)
    # ...analyze and resolve...
    write_file(file, resolution)
    submit_resolution(file)

# All files submitted, validate as batch
result = run_check('normal')

if 'FAILED' in result:
    # One of the files broke build
    # Analyze error, identify which file
    # Re-read, re-resolve, re-submit that file
    ...
```

### Pattern 3: Progressive Validation
```python
# Resolver working on large conflict

# Start with quick syntax check
write_file('SelectionDAG.cpp', initial_resolution)
result = run_check('quick')

if 'PASSED' in result:
    # Syntax good, submit
    submit_resolution('SelectionDAG.cpp')

    # Now run full build to catch semantic issues
    result = run_check('normal')

    if 'FAILED' in result:
        # Semantic error (like duplicate case)
        # Need to re-open and fix
        read_file('SelectionDAG.cpp')
        # ...fix...
        write_file('SelectionDAG.cpp', fixed)
        submit_resolution('SelectionDAG.cpp')
```

## Open Questions

### 1. Check Level Intelligence
Should the tool:
- Accept any string and look it up in config? (flexible)
- Validate against known levels and suggest alternatives? (helpful)
- Have semantic meanings ('quick' always means syntax)? (limiting)

**Recommendation**: Accept any string from config, error with available options if not found.

### 2. Partial Failure Handling
If check fails, should Resolver:
- Always fix immediately? (might loop forever)
- Be allowed to submit anyway and let Coordinator retry batch? (pragmatic)
- Have a retry budget per conflict? (complex)

**Recommendation**: Let Resolver decide. It can submit and move on, or fix and retry. Trust the LLM's judgment.

### 3. Check Result Caching
If Resolver runs `run_check('quick')` twice in a row without changing files:
- Should it return cached result? (faster, cheaper)
- Should it run again? (more accurate)

**Recommendation**: Don't cache. If Resolver calls it twice, it wants two checks.

### 4. Timeout Handling
If check times out (exceeds config.check.timeout):
- Return "TIMEOUT" as failure? (clear signal)
- Raise exception? (might abort entire merge)

**Recommendation**: Return as failure with "TIMEOUT" message. Resolver can decide to retry or continue.

### 5. Multiple Simultaneous Checks
Can Resolver run multiple checks in parallel:
```python
quick_result = run_check('quick')  # Syntax check
normal_result = run_check('normal')  # Full build
```

**Recommendation**: No. Tools are synchronous and sequential. Would need special orchestration.

## Success Criteria

The `run_check` tool is successful if:

1. **Resolvers use it appropriately** (after risky changes, not excessively)
2. **Catches issues early** (before 50 more conflicts resolved)
3. **Provides actionable feedback** (Resolver can fix based on error output)
4. **Doesn't slow merges too much** (intelligent check level selection)
5. **Integrates cleanly** (uses existing CheckRunner, consistent with workflow checks)

## Migration Path

This is a **new capability** - no migration needed.

**Before**: Resolver submits all resolutions, hopes Coordinator/workflow catches issues later

**After**: Resolver can validate its work immediately when uncertain or after critical changes

**Backward compatible**: Not using the tool is fine, workflow checks still happen.