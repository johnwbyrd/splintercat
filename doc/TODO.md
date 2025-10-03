# Splintercat Design Document

## Current Implementation Status

**Completed Components:**
- ✅ CommandRunner - stdin support, real-time output, interactive mode
- ✅ Result value object - command execution results
- ✅ Patch value object - dataclass with lazy properties (author, files, subject, timestamp)
- ✅ Config (pydantic-settings) - YAML + env vars + CLI args
- ✅ Logging (loguru) - colored console + file rotation
- ✅ GitSource - fetches patches via git format-patch, returns PatchSet
- ✅ GitTarget - applies with git am (preserves authorship), atomic test cycle
- ✅ PatchSet - single concrete class (needs simplification from current ABC)

**To Do:**
- ❌ State - Pydantic model for strategy state management
- ❌ Strategy - pure function interface with State
- ❌ Main loop - wire everything together

## Architecture

### File Structure

```
splintercat/
├── main.py                    # Entry point - main loop
├── config.yaml                # Configuration
├── pyproject.toml             # Dependencies, ruff config
├── .gitignore
├── README.md
├── doc/
│   └── TODO.md                # This file
│
└── src/
    ├── __init__.py
    │
    ├── core/
    │   ├── __init__.py
    │   ├── command_runner.py  # ✅ CommandRunner class
    │   ├── config.py          # ✅ Settings (pydantic-settings)
    │   ├── log.py             # ✅ Logging setup (loguru)
    │   ├── patch.py           # ✅ Patch dataclass
    │   ├── result.py          # ✅ Result value object
    │   ├── source.py          # ✅ Source ABC + GitSource
    │   ├── target.py          # ✅ Target ABC + GitTarget
    │   └── state.py           # ❌ State and Result models
    │
    ├── patchset/
    │   ├── __init__.py
    │   └── patchset.py        # ⏸️ Single PatchSet class (simplify from current)
    │
    └── strategy/
        ├── __init__.py
        ├── base.py            # ❌ Strategy ABC
        ├── sequential.py      # ❌ SequentialStrategy
        └── bisect.py          # ❌ BisectStrategy (future)
```

## Core Design Principles

### 1. YAGNI (You Aren't Gonna Need It)
- Start with simplest implementation that works
- Add complexity only when actually needed
- Single PatchSet class, not 4+ implementations
- Can extend later if requirements emerge

### 2. Optimistic First Attempt
- Always try ALL patches first (best case: one build and done)
- Only subdivide/skip on failure
- Strategy gets full history to make intelligent decisions

### 3. Pure Functions Where Possible
- Strategy is stateless - pure function from State → PatchSet
- All state lives in State object
- Enables reasoning, testing, persistence

### 4. Preserve Attribution
- Use `git am` not `git apply` - preserves original authorship
- No rewriting unless absolutely necessary
- Separate commit for our modifications if needed

## Component Definitions

### Patch (Value Object)

Dataclass representing a single patch from git format-patch.

**Fields:**
- `id: str` - Git commit hash
- `diff: str` - Full patch text (mbox format)
- `metadata: dict` - Extensible metadata storage

**Lazy Properties** (via @cached_property):
- `author` - parsed from "From:" header
- `timestamp` - parsed from "Date:" header
- `changed_files` - parsed from diff headers
- `subject` - parsed from "Subject:" header

**Design Notes:**
- Immutable after creation (metadata dict is mutable for annotations)
- Properties cached after first access
- No methods - pure data object

### PatchSet (Collection Wrapper)

Lightweight wrapper around `list[Patch]` with efficient slicing.

**Key Methods:**
- `__init__(patches, start, end)` - wrap a list with optional range
- `slice(start, end)` - O(1) sub-range extraction
- `__iter__()` - iterate patches
- `size()` - count patches
- `get(index)` - retrieve single patch

**Design Notes:**
- Single concrete class (not ABC + implementations)
- O(1) slicing via (source, start, end) indices
- Shares underlying list - no copying
- Can add filter/union/compose methods later if needed (YAGNI)

**Why not just list[Patch]?**
- O(1) slicing without copying (important for bisection)
- Clean API for strategies
- Can extend with smart operations later

### State (Strategy State Management)

Pydantic models for tracking all attempts and results.

**Result Model:**
- `patch_ids` - which patches were attempted
- `success` - did apply + test succeed?
- `timestamp`, `duration_apply`, `duration_test` - timing info
- `apply_output`, `test_output` - full command output
- `error_message` - if failed

**State Model:**
- `original_patchset` - all patches from source
- `results` - history of all attempts
- `done` - strategy sets when complete
- `record_result(patchset, success, **details)` - add attempt to history

**Design Notes:**
- State is passed to Strategy, not owned by it
- Strategy is pure function: State → PatchSet | None
- Result captures everything about one attempt (for analysis/debugging)
- Can persist State to database for learning across runs (future)

**PatchSet Serialization:**
- For now, State lives only in memory during one run
- When we add database (Level 3), we'll store patch_ids and results
- PatchSet can be reconstructed from original_patchset + IDs

### Source (Produces Patches)

Abstract interface for fetching patches from various sources.

**Source ABC:**
- `get_patches()` → PatchSet

**GitSource Implementation:**
- `__init__(config, runner)` - setup with config and command runner
- `get_patches()` → PatchSet

**GitSource Workflow:**
1. Fetch from remote (`git fetch`)
2. Find merge-base (`git merge-base HEAD FETCH_HEAD`)
3. List commits chronologically (`git rev-list --reverse`)
4. Generate patches (`git format-patch -1 --stdout {commit}`)
5. Wrap in PatchSet and return

**Responsibilities:**
- Load patches from external source (git, email, directory, etc.)
- Parse into Patch objects
- Return as PatchSet

**Not Responsible For:**
- Deciding which patches to apply (Strategy's job)
- Testing patches (Target's job)

### Target (Applies and Tests Patches)

Abstract interface for applying patches and testing them.

**Target ABC:**
- `checkout()` - prepare target branch
- `try_patches(patchset)` → bool - atomic apply+test+rollback
- `commit(message)` - commit applied patches

**GitTarget Implementation:**
- `__init__(config, test_cmd, runner)` - setup
- Implements all Target methods

**GitTarget.try_patches() - Atomic Operation:**
1. Save current state (`git rev-parse HEAD`)
2. Apply patches via stdin (`git am` - preserves authorship!)
3. Run test command (build, test suite, etc.)
4. On success: return True (patches already committed by git am)
5. On failure: rollback (`git reset --hard && git clean -fd`), return False

**Key Design Decisions:**
- **Uses git am, not git apply** - preserves original author/date/message
- **Atomic from Strategy's perspective** - either all patches work or all are rolled back
- **commit() is no-op** - git am already committed with proper attribution
- **Target decides build strategy** - clean vs incremental, test command, etc.

**Responsibilities:**
- Complete test cycle (apply + build + test + rollback)
- State management (save/restore git state)
- All git operations

**Not Responsible For:**
- Deciding which patches to try (Strategy's job)
- Splitting/ordering patches (Strategy's job)

### Strategy (Decides What to Try)

Pure function that analyzes State and returns next PatchSet to try.

**Strategy ABC:**
- `next_attempt(state)` → PatchSet | None - decide what to try next

**SequentialStrategy:**
- First attempt: try all patches (optimistic)
- If that works: done!
- Otherwise: try one patch at a time
- Give up when all patches tried

**BisectStrategy (Future):**
- First attempt: try all patches (optimistic)
- If that works: done!
- Otherwise: maintain work queue of ranges
- Split failed ranges in half
- Continue until all ranges tested or give up

**Key Design Decisions:**
- **Strategy is stateless** - all state in State object
- **Strategy is pure function** - deterministic, testable
- **Strategy decides when to give up** - sets state.done = True
- **Optimistic first** - always try all patches first
- **Full history available** - Strategy sees all previous attempts

**Responsibilities:**
- Decide which patches to try next
- Decide when to give up
- Analyze history to make intelligent decisions
- Control splitting/ordering logic

**Not Responsible For:**
- Applying/testing patches (Target's job)
- Loading patches (Source's job)

## Data Flow

**Main Loop:**
1. Setup - load config, initialize logging, create runner/source/target/strategy
2. Get patches - source.get_patches() → PatchSet
3. Initialize state - State(original_patchset=patches)
4. Prepare target - target.checkout()
5. Loop until done:
   - Strategy decides next attempt: strategy.next_attempt(state) → PatchSet
   - Target tries patches: target.try_patches(patchset) → bool
   - Record result: state.record_result(patchset, success, ...)
6. Report final results

**Key Insights:**
- Patches loaded ONCE from source
- Strategy has full history to make decisions
- Target.try_patches() is atomic (apply+test+rollback)
- Strategy controls everything: what to try, when to give up
- State contains complete audit trail

## Design Choices

1. **Single PatchSet Class (YAGNI)**
   - Start simple, add specialized types (Indexed, Composed, Lazy) only if needed
   - Current needs met by simple wrapper with O(1) slicing

2. **Strategy is Pure Function**
   - All state in State object, not in Strategy instance
   - Enables testing, reasoning, future database persistence
   - Strategy instances can be stateless/reusable

3. **Optimistic First Attempt**
   - Best case: try all 6439 patches, everything works, done in one build
   - Only subdivide on failure
   - Huge time savings when upstream is stable

4. **git am for Attribution**
   - Preserves original author, date, commit message
   - No rewriting needed
   - commit() is no-op since git am commits automatically

5. **Complete Build Logs in Result**
   - Every build attempt fully logged
   - Enables debugging, analysis, future ML
   - Configurable retention (log rotation)

6. **Pydantic for Everything**
   - Type-safe configuration (Settings)
   - Type-safe state (State, Result)
   - Validation built-in
   - Easy serialization for future database

## Implementation Phases

### Phase 1: Core Components (In Progress)
**Status:** Most components complete, need State and Strategy

**Completed:**
- ✅ Project structure (src/core, src/patchset, src/strategy)
- ✅ Dependencies (pydantic, pydantic-settings, loguru)
- ✅ CommandRunner with stdin, real-time output
- ✅ Result value object
- ✅ Patch dataclass with lazy properties
- ✅ Settings (pydantic-settings) with YAML/env/CLI
- ✅ Logging (loguru) with console + file
- ✅ GitSource with git format-patch
- ✅ GitTarget with git am (preserves attribution)
- ⏸️ PatchSet (needs simplification - remove ABC)

**To Do:**
- ❌ Simplify PatchSet (single class, not ABC)
- ❌ Implement State and Result (Pydantic models)
- ❌ Implement Strategy ABC
- ❌ Implement SequentialStrategy
- ❌ Wire up main.py
- ❌ Test with small patch count

**Success Criteria:** Works like original main.py but with new architecture

### Phase 2: Bisect Strategy
**Goal:** Add divide-and-conquer for faster processing

1. Implement BisectStrategy
2. Test with small patch count
3. Test with full 6439 patches
4. Compare performance vs Sequential

**Success Criteria:** Can handle 6439 patches in O(log n) builds

### Phase 3: Database Persistence (README Level 3)
**Goal:** Learn from history across runs

1. Add SQLite database
2. Persist State.results to database
3. Track success/failure patterns
4. Skip known-bad patches on subsequent runs
5. Add success rate statistics by author, file, time period

**Success Criteria:** Learns patterns, improves over multiple runs

### Phase 4: Smart Filtering (README Level 4)
**Goal:** Intelligent patch selection

1. Add IndexedPatchSet for filtering
2. Implement filter by author, files, success probability
3. Reorder patches by predicted success
4. Look-ahead: try adding later patches to fix failures

**Success Criteria:** Recovers >50% of initially skipped patches

### Phase 5: LLM Rewriting (README Level 5)
**Goal:** Adapt patches to current codebase

1. Add LazyPatchSet for generated patches
2. Integrate LLM API for patch rewriting
3. Cache rewrites in database
4. Only rewrite high-value patches (not all 6439!)

**Success Criteria:** Can rewrite and apply previously-failing patches

### Phase 6: ML Prediction (README Level 6)
**Goal:** Predict patch success probability

1. Train model on historical data
2. Predict success for each patch
3. Sort patches by predicted success
4. Optimize for maximum patches per build

**Success Criteria:** Maximizes throughput via learned patterns

## Future Extensions

### Parallel Application
- Test independent patches in parallel branches
- Requires dependency analysis (file overlap detection)
- Merge successful branches
- Could use ComposedPatchSet for combinations

### Custom Strategies
- Dependency-aware grouping
- Time-based filtering (try recent patches first)
- Author-based trust scores
- File-based grouping (all clang patches together)

### Advanced Metadata
- Parse patch dependencies from comments
- Detect fix/revert relationships
- Track file-level conflict patterns
- Author collaboration graphs

## Success Metrics

**Phase 1:** Feature parity with original, cleaner architecture
**Phase 2:** 6439 patches in <100 builds (vs 6439 sequential)
**Phase 3:** Learns patterns, improves on subsequent runs
**Phase 4:** Recovers >50% of skipped patches via intelligent ordering
**Phase 5:** Successfully rewrites and applies previously-failing patches
**Phase 6:** Maximizes patch throughput via ML predictions
