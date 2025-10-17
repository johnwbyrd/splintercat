# Coordinator Agent Design

## Problem Statement

The current strategy system (optimistic, batch, per-conflict) uses hardcoded logic to decide when to validate work:
- **Optimistic**: Never check until all conflicts resolved
- **Batch**: Count to N conflicts, then check
- **PerConflict**: Check after every conflict

This is inflexible. An intelligent system should make context-aware decisions:
- "These 10 conflicts were all in docs - keep going"
- "Just touched core IR - better validate now"
- "Build failed in this module before - check more frequently"
- "5 conflicts left and all low-risk - finish then validate"

## Proposal: Replace Strategy with Coordinator LLM

The Coordinator Agent orchestrates the entire merge workflow. It makes high-level decisions about what happens next based on current state, not hardcoded rules.

## Coordinator Responsibilities

### Primary Job
Make workflow routing decisions:
1. **When to resolve more conflicts** (and how many)
2. **When to run validation checks** (and which level)
3. **When the merge is complete** and ready to finalize
4. **When to request human intervention**

### NOT Coordinator's Job
- Resolving individual conflicts (that's Resolver's job)
- Reading/writing code files (operates at workflow level)
- Diagnosing build failures (that's Diagnostic Agent's job)

## Coordinator Tools

The Coordinator needs tools to:
1. **Query current state**
2. **Control workflow progression**

### Tool: `get_merge_status() -> dict`

Returns current merge state:
```python
{
    "total_conflicts": 47,
    "conflicts_resolved": 23,
    "conflicts_remaining": 24,
    "current_batch": {
        "conflicts_in_batch": 5,
        "files_touched": ["lib/IR/Globals.cpp", "lib/IR/Constants.cpp"],
        "started_at": "2025-10-16T21:10:00"
    },
    "last_check": {
        "level": "normal",
        "result": "passed",
        "timestamp": "2025-10-16T21:08:15"
    },
    "retry_count": 0,
    "max_retries": 3
}
```

### Tool: `get_conflict_preview(count: int = 5) -> list[dict]`

Peek at next N conflicts without resolving them:
```python
[
    {
        "pair": (12, 5),
        "files": ["docs/UserGuide.md", "docs/Installation.md"],
        "estimated_risk": "low"  # Based on file type, location
    },
    {
        "pair": (12, 6),
        "files": ["lib/CodeGen/SelectionDAG.cpp"],
        "estimated_risk": "high"  # Core functionality
    },
    ...
]
```

### Tool: `resolve_conflicts(count: int, reason: str) -> str`

Signal workflow to resolve next N conflicts:
```python
resolve_conflicts(
    count=10,
    reason="Next 10 conflicts are all documentation, low risk"
)
# Returns: "Resolving 10 conflicts. Will return here afterward."
```

**Note**: This is **non-blocking from Coordinator's perspective**. It signals the workflow graph to route to ResolveConflicts node. After those conflicts are resolved, workflow returns to Coordinator for next decision.

### Tool: `run_checks(levels: list[str], reason: str) -> str`

Signal workflow to run validation checks:
```python
run_checks(
    levels=["normal"],
    reason="Just resolved 5 high-risk IR files, validate before continuing"
)
# Returns: Summary of check results
```

**Synchronous**: Blocks until checks complete, returns pass/fail summary.

### Tool: `finalize_merge(reason: str) -> str`

Signal merge is complete, create final commit:
```python
finalize_merge(
    reason="All 47 conflicts resolved, final check passed, ready to commit"
)
# Returns: "Merge finalized. Final commit: abc123"
```

### Tool: `request_manual_intervention(reason: str, context: dict) -> None`

Stop workflow and ask for human help:
```python
request_manual_intervention(
    reason="Build failures persist after 3 retries on same module",
    context={
        "failing_check": "normal",
        "error_summary": "Duplicate case in switch statement",
        "attempted_fixes": 3,
        "diagnostic_log": "/path/to/diagnosis.txt"
    }
)
# Raises exception that halts workflow with structured explanation
```

## Coordinator Prompt Design

### System Prompt

```
You are a Coordinator Agent that orchestrates git merge workflows.

Your job: Decide the next step in the merge process based on current state.

AVAILABLE TOOLS:
- get_merge_status(): See current progress, batch info, check results
- get_conflict_preview(count): Peek at upcoming conflicts
- resolve_conflicts(count, reason): Resolve next N conflicts
- run_checks(levels, reason): Run validation (quick/normal/full)
- finalize_merge(reason): Create final merge commit
- request_manual_intervention(reason, context): Ask for human help

DECISION FACTORS:
1. Risk level of files involved (core IR vs docs vs tests)
2. Current batch size and diversity
3. Recent check results and failure patterns
4. Retry count and failure recovery
5. Conflicts remaining vs already resolved

EXAMPLES OF GOOD DECISIONS:

Scenario: 10 doc conflicts resolved, 20 more doc conflicts ahead
Decision: resolve_conflicts(20, "All documentation, low risk, efficient to batch")

Scenario: Just resolved lib/IR/Globals.cpp (high risk)
Decision: run_checks(["normal"], "Critical IR file touched, validate immediately")

Scenario: 3 retries failed on same module with same error
Decision: request_manual_intervention("Repeated failures suggest semantic conflict")

Scenario: 2 conflicts left, both in tests, last check passed
Decision: resolve_conflicts(2, "Almost done, finish remaining low-risk conflicts")
         → Then: run_checks(["full"], "Final validation before merge")
         → Then: finalize_merge("All conflicts resolved, tests pass")

WHEN TO CHECK:
- After resolving high-risk files (IR, CodeGen, core APIs)
- When batch gets large (>10-15 conflicts without validation)
- After resolver explicitly requests check via run_check tool
- Before finalizing (final comprehensive validation)

WHEN TO REQUEST HELP:
- Retry limit exceeded with no progress
- Diagnostic agent can't identify root cause
- Semantic conflicts that resolver can't fix
- Build failures in areas outside conflict scope
```

## Workflow Integration

### Current Flow (Strategy-Based)
```
Initialize
  ↓
ResolveConflicts (resolves until strategy.should_check_now())
  ↓
Check (runs checks)
  ↓ (based on result and conflicts_remaining)
ResolveConflicts or Finalize
```

### Proposed Flow (Coordinator-Based)
```
Initialize
  ↓
┌─> CoordinateNextStep (Coordinator decides what's next)
│     ↓
│   Routes based on decision:
│     ├─> ResolveConflicts(count=N) ───┐
│     ├─> Check(levels=[...]) ─────────┤
│     ├─> Finalize ────────────────────┘
│     └─> ManualIntervention (raises exception)
│
└─────┘ (loops back to CoordinateNextStep after each action)
```

Every action returns to Coordinator for next decision.

## Coordinator vs Resolver Separation

| Aspect | Coordinator Agent | Resolver Agent |
|--------|------------------|----------------|
| **Scope** | Entire merge workflow | Single conflict pair (i1, i2) |
| **Context** | All conflicts, batch history, check results | Just files with conflicts in current pair |
| **Decisions** | What to do next (resolve/check/finalize) | How to merge conflicting code |
| **Tools** | get_status, resolve_conflicts, run_checks, finalize | read_file, write_file, run_command, submit_resolution |
| **Runs** | Once per workflow step | Once per conflict pair |
| **State** | Reads full MergeState | Reads/writes Workspace |

They are **separate agent instances** with different prompts, tools, and contexts.

## Coordinator vs Diagnostic Agent Relationship

When checks fail, the workflow routes to Diagnostic Agent:

```
CoordinateNextStep
  ↓
run_checks(["normal"])
  ↓ (check fails)
DiagnosticAgent analyzes log
  ↓
Returns diagnosis to Coordinator
  ↓
Coordinator decides:
  ├─> resolve_conflicts (retry with error context)
  ├─> PostMergeDebug (semantic conflict fix)
  └─> request_manual_intervention (can't fix)
```

The Diagnostic Agent **feeds information to** the Coordinator, which then makes the routing decision.

## Configuration Changes

### Remove
```yaml
config:
  strategy:
    name: batch          # DELETE - Coordinator decides
    batch_size: 10       # DELETE - Coordinator chooses dynamically
```

### Keep
```yaml
config:
  strategy:
    max_retries: 3       # KEEP - Safety limit
```

### Add (Optional)
```yaml
config:
  coordinator:
    model: openai/gpt-4o              # Can use different model than resolver
    risk_thresholds:                  # Hints for coordinator decisions
      high_risk_paths: ["lib/IR/*", "lib/CodeGen/*"]
      low_risk_paths: ["docs/*", "test/*"]
    max_batch_size: 20                # Safety limit
    min_check_frequency: 15           # Check at least every N conflicts
```

## Example Coordinator Reasoning

### Scenario 1: Documentation Conflicts
```
get_merge_status()
# Returns: 15 conflicts resolved, 25 remaining

get_conflict_preview(10)
# Returns: Next 10 are all docs/*.md files

# Coordinator reasoning:
"Documentation files are low risk. No checks needed yet.
Efficient to resolve in larger batches."

resolve_conflicts(10, "All documentation, low risk")
```

### Scenario 2: Critical File Touched
```
get_merge_status()
# Returns: Just resolved lib/IR/Globals.cpp in current batch

# Coordinator reasoning:
"IR files are high risk. Only 3 conflicts in batch but
Globals.cpp is critical. Better validate now before continuing."

run_checks(["normal"], "Critical IR file modified, validate early")
```

### Scenario 3: Check Failed
```
run_checks(["normal"])
# Returns: FAILED - duplicate case statement in Globals.cpp

get_merge_status()
# Returns: retry_count = 1, max_retries = 3

# Coordinator reasoning:
"Build failed but we have retry budget. Diagnostic agent
will analyze. Let's retry the batch with error context."

# Workflow automatically routes to Diagnostic → PostMergeDebug
# Coordinator waits for fix, then decides next step
```

### Scenario 4: Near Completion
```
get_merge_status()
# Returns: 45 resolved, 2 remaining

get_conflict_preview(2)
# Returns: Both in test/*.cpp

# Coordinator reasoning:
"Almost done. Finish the last 2 conflicts, then run full
validation before finalizing."

resolve_conflicts(2, "Last 2 conflicts, both in tests")
# After resolution:
run_checks(["full"], "Final comprehensive validation")
# After checks pass:
finalize_merge("All conflicts resolved, full test suite passes")
```

## Open Questions

### 1. Coordinator Model Selection
Should Coordinator use:
- Same model as Resolver? (simpler, cheaper)
- Faster/cheaper model? (decisions are simpler than resolution)
- Smarter model? (better strategic thinking)

**Recommendation**: Start with same model, make configurable later.

### 2. Coordinator State Persistence
If merge takes hours/days:
- Should Coordinator decisions be logged for resume?
- Should Coordinator see its own previous decisions?
- How to handle workflow resume after interruption?

**Recommendation**: Log all decisions to state, pass history in context.

### 3. Conflict Risk Assessment
How to estimate conflict risk without resolving?
- File path patterns (IR vs docs vs tests)
- File size / change size
- Historical data (this file broke builds before)

**Recommendation**: Start simple (path patterns), add heuristics as needed.

### 4. Coordinator Override
Should users be able to:
- Set minimum check frequency (check at least every N conflicts)?
- Set maximum batch size (never resolve more than M conflicts)?
- Force specific check points (always check after IR files)?

**Recommendation**: Add optional safety limits in config.

### 5. Diagnostic Integration
When checks fail:
- Does Coordinator call Diagnostic Agent directly?
- Or does workflow automatically route to Diagnostic?
- Who decides retry vs manual intervention?

**Recommendation**: Workflow routes to Diagnostic automatically, Diagnostic reports back to Coordinator, Coordinator makes final decision.

## Implementation Phases

### Phase 1: Basic Coordinator (Replaces Strategy)
- Implement coordinator agent with basic tools
- Remove strategy classes
- Simple workflow: CoordinateNextStep → ResolveConflicts/Check/Finalize

### Phase 2: Smart Decisions
- Add conflict preview
- Add risk assessment heuristics
- Tune coordinator prompt based on real merges

### Phase 3: Diagnostic Integration
- Add Diagnostic Agent
- PostMergeDebug workflow
- Coordinator handles check failures intelligently

### Phase 4: Advanced Features
- Configurable risk patterns
- Historical data (this file caused issues before)
- Learning from past merge patterns

## Success Metrics

The Coordinator is successful if:
1. **Makes intelligent batching decisions** (large batches for low-risk, small for high-risk)
2. **Validates at appropriate times** (not too often, not too rarely)
3. **Handles failures gracefully** (retries, requests help when needed)
4. **Completes merges faster** than fixed strategy (fewer unnecessary checks)
5. **Catches issues early** (before entire merge fails)

## Migration Path

For users currently using strategies:

**Old config**:
```yaml
strategy:
  name: batch
  batch_size: 10
```

**Transition**: Coordinator sees this in config and uses it as a hint:
```
"User previously used batch size 10. Start with that as baseline,
adjust based on file risk and check results."
```

**Future**: Eventually remove strategy config entirely, Coordinator decides everything.
