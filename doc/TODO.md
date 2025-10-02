# Splintercat Refactor Design Document

## Current State

**What we have:**
- Single `main.py` (195 lines) with all logic
- CommandRunner, Source, Target, Strategy classes inline
- Working implementation: fetches patches, applies sequentially, tests each
- Patches loaded from git, passed as dicts with `{id, diff}` structure
- Config-driven git commands via YAML

**What works:**
- Fetches patches from upstream git repo
- Applies patches one-by-one to target branch
- Tests each with build command (ninja)
- Commits successes, rolls back failures
- CommandRunner handles stdin properly (no shell escaping issues)

**What's limiting:**
- No abstraction for patch collections (just raw lists)
- No metadata tracking (author, files changed, dependencies)
- Only sequential strategy implemented
- Can't compose or reorder patches
- All 6439 patches would take linear time to process

## Architecture Refactor

### File Structure

```
splintercat/
├── main.py                    # Entry point only (~20 lines)
├── config.yaml
├── requirements.txt
├── README.md
├── TODO.md                    # This file
│
└── src/
    ├── __init__.py
    │
    ├── core/
    │   ├── __init__.py
    │   ├── command_runner.py  # CommandRunner class
    │   ├── config.py          # Load from YAML + CLI args (argparse)
    │   ├── logging.py         # Logging setup and utilities
    │   ├── patch.py           # Patch value object
    │   ├── result.py          # Result, TestResult value objects
    │   ├── source.py          # Source ABC + GitSource implementation
    │   └── target.py          # GitTarget implementation
    │
    ├── patchset/
    │   ├── __init__.py
    │   ├── base.py            # PatchSet ABC
    │   ├── range.py           # RangePatchSet (contiguous, O(1) split)
    │   ├── indexed.py         # IndexedPatchSet (filtered, reordered)
    │   ├── composed.py        # ComposedPatchSet (union of sets)
    │   └── lazy.py            # LazyPatchSet (generated on demand)
    │
    └── strategy/
        ├── __init__.py
        ├── base.py            # Strategy ABC
        ├── sequential.py      # Current implementation
        └── bisect.py          # Divide-and-conquer (future)
```

### Why This Structure

- **src/**: All Python source code
- **core/**: Core functionality (command running, config, logging, git operations, value objects)
- **patchset/**: Abstraction for patch collections (multiple implementations)
- **strategy/**: Decision logic for applying patches (multiple implementations)

## PatchSet Abstraction

### Abstract Base Class Interface

- `size()` - count patches
- `get(index)` - retrieve single patch
- `__iter__()` - iterate patches
- `to_list()` - convert to List[Patch] for passing to Target
- `slice(start, end)` - extract contiguous range (returns new PatchSet)
- `filter(predicate)` - select patches matching condition (returns new PatchSet)
- `union(other)` - combine two PatchSets (returns new PatchSet)
- `annotate(key, value_fn)` - attach metadata (returns new PatchSet)
- `metadata(index, key)` - retrieve attached metadata

**Key design decisions:**
- **Immutable operations**: filter/slice/union return NEW PatchSets
- **Shared source**: All PatchSets reference same underlying List[Patch]
- **Lazy metadata**: Computed on demand, cached on Patch objects
- **No split()**: Strategy decides how to divide PatchSets (binary, n-way, by-dependency)
- **No test()**: Target is responsible for testing patches

### Concrete Implementations

#### RangePatchSet
**Purpose:** Contiguous ranges for bisection
**Storage:** `(source: List[Patch], start: int, end: int)`
**Strengths:**
- O(1) slice and split operations
- Minimal memory overhead
- Natural for sequential/bisect strategies

**Use cases:**
- Bisection: Strategy repeatedly slices in half
- Sequential: process range start to end
- Initial load: all patches as one range

**Example split patterns (Strategy decides):**
- Binary: split at midpoint
- N-way: divide into N equal chunks
- By-dependency: analyze changed files, group related patches

#### IndexedPatchSet
**Purpose:** Arbitrary subsets for filtering
**Storage:** `(source: List[Patch], indices: List[int])`
**Strengths:**
- Efficient filtering (just modify index list)
- Can reorder patches
- Can skip patches (e.g., "no Hank")

**Use cases:**
- Filter by author: `filter(lambda p: p.author != 'Hank')`
- Sort by predicted success: `sorted(key=lambda p: p.metadata['score'])`
- Skip known-bad patches from database

#### ComposedPatchSet
**Purpose:** Union/combination of other PatchSets
**Storage:** `children: List[PatchSet]`
**Strengths:**
- Arbitrary reordering: patches[1-100] + patches[500] + patches[101-200]
- Look-ahead fixes: broken range + potential fix patch
- Lazy evaluation: only test when needed

**Use cases:**
- "Try these patches with this fix patch inserted"
- Reorder based on dependency analysis
- Compose results from multiple strategies

#### LazyPatchSet
**Purpose:** Generated/rewritten patches
**Storage:** `generator: Callable[[], List[Patch]]`
**Strengths:**
- Don't generate until needed
- LLM rewrites only for failures
- Can cache results

**Use cases:**
- LLM-rewritten patches (future)
- Dynamically generated alternatives
- Expensive transformations

### Patch Value Object

Uses Python stdlib `@dataclass` (NOT Pydantic - no external deps beyond pyyaml)

**Fields:**
- `id: str` - Git commit hash
- `diff: str` - Full patch text
- `metadata: Dict[str, Any]` - Extensible metadata storage

**Lazy-computed properties (cached after first access):**
- `author` - parsed from diff
- `changed_files` - parsed from diff
- `timestamp` - parsed from diff

**Design notes:**
- Python 3.7+ stdlib dataclass, functools.cached_property from 3.8+
- Immutable after creation (frozen=False allows metadata updates)
- Metadata dict for extensibility (predictions, skip reasons, etc.)
- Expensive parsing cached as properties
- No methods - pure data object

## Component Definitions

### Source (Produces Patches)

**Interface:** `get_patches() -> List[Patch]`

**GitSource implementation:**
- Fetch from remote
- Find merge-base
- List commits chronologically (earliest first)
- Generate patches via git format-patch
- Return List[Patch]

**Responsibilities:**
- Load patches from external source (git, email, directory, etc.)
- Parse into Patch objects
- Return complete list (read once, use many times)

**Not responsible for:**
- Deciding which patches to apply
- Testing patches
- Metadata extraction beyond basic parsing

### Target (Applies and Tests Patches)

**GitTarget** - Concrete class (assumes git)

Target knows HOW to test (clean build? incremental? what test command?).
Strategy knows WHICH patches to test.

**Interface:**
- `checkout()` - Prepare target branch (create if needed, checkout if exists)
- `try_patches(patches: List[Patch]) -> bool` - Complete atomic test cycle
- `commit(message: str)` - Commit applied patches

**try_patches() behavior (atomic from Strategy's perspective):**
1. Save current state (git rev-parse HEAD)
2. Apply patches (git apply via stdin)
3. Run build (ninja, make, etc. - Target decides clean vs incremental)
4. Run test (configured test command)
5. On any failure: rollback (git reset --hard + git clean -fd)
6. Return bool (success/failure)

**Responsibilities:**
- **Complete test cycle**: apply + build + test + rollback as single operation
- **Build strategy**: Target decides clean vs incremental builds
- **State management**: save/restore git state, clean untracked files
- **Git operations**: All git commands encapsulated here (assumes git!)

**Not responsible for:**
- Deciding which patches to try (Strategy's job)
- Splitting/ordering patches (Strategy's job)
- Loading patches from source (Source's job)

### Strategy (Decides What to Try)

**Interface:** `apply(patchset: PatchSet, target: GitTarget) -> ApplyResult`

**SequentialStrategy:**
- Try each patch once, in order
- Call `target.try_patches([patch])` for each
- On success: commit
- On failure: skip, continue

**BisectStrategy:**
- Try whole range with `target.try_patches(patchset.to_list())`
- If success: commit all
- If failure: split into N subsets (binary, n-way, etc.)
- Recurse on each subset
- Strategy controls splitting (not PatchSet)

**Splitting examples (Strategy decides):**
- Binary split: divide at midpoint
- N-way split: divide into N equal chunks
- Dependency-aware: analyze changed files, group related patches
- Hybrid: bisect first, then sequential on small ranges

**Responsibilities:**
- Decide which patches to try
- Order of attempts
- How to split PatchSets (binary, n-way, by-dependency)
- How to handle failures (skip, retry, etc.)
- Composition of PatchSet operations (slice/filter/union)

**Not responsible for:**
- Actually applying/testing patches (Target does this via try_patches())
- Loading patches (Source does this)
- Parsing patch content

## Data Flow

1. Source loads patches from git → List[Patch] (6439 patches in memory)
2. Strategy wraps in PatchSet → RangePatchSet(patches, 0, 6439)
3. Strategy decides approach → split into subsets, or filter, or sequential
4. Strategy calls Target → `target.try_patches(patchset.to_list())`
5. Target executes complete cycle → apply + build + test + rollback on failure
6. Target returns bool → success/failure
7. Strategy decides next action → commit, re-split, skip
8. Repeat until done

**Key insights:**
- Patches loaded ONCE, then manipulated via PatchSet views
- Target.try_patches() is atomic from Strategy's perspective
- Strategy controls all splitting decisions
- Results are binary (success/failure)

## Implementation Phases

### Phase 1: Extract Classes (No Behavior Change)
**Goal:** Split main.py into modules, keep everything working

1. Create directory structure (src/core/, src/patchset/, src/strategy/)
2. Move CommandRunner → `src/core/command_runner.py`
3. Move Result → `src/core/result.py`
4. Move Source → `src/core/source.py` (rename current Source to GitSource)
5. Move Target → `src/core/target.py` (rename to GitTarget)
6. Move Strategy → `src/strategy/sequential.py` (rename to SequentialStrategy)
7. Create `src/core/config.py` to load YAML + parse CLI args (merge these concerns)
8. Create `src/core/logging.py` for logging setup
9. Update main.py to import from src.* modules
10. Test: should work identically

**Success criteria:** `python main.py` works exactly as before

### Phase 2: Introduce Patch Value Object
**Goal:** Replace `{id, diff}` dicts with Patch dataclass

1. Create `src/core/patch.py` with Patch dataclass
2. Update GitSource.get_patches() to return List[Patch]
3. Update GitTarget to accept List[Patch]
4. Update SequentialStrategy to work with Patch objects
5. Test: should work identically

**Success criteria:** Same behavior, cleaner types

### Phase 3: Create PatchSet Abstraction
**Goal:** Introduce PatchSet without changing strategy behavior

1. Create `patchset/base.py` with PatchSet ABC
2. Create `patchset/range.py` with RangePatchSet
3. Update SequentialStrategy to accept PatchSet instead of List[Patch]
4. Wrap loaded patches in RangePatchSet in main()
5. Test: should work identically

**Success criteria:** Same behavior, PatchSet in place

### Phase 4: Implement Additional PatchSets
**Goal:** Enable filtering and composition

1. Create `patchset/indexed.py` with IndexedPatchSet
2. Create `patchset/composed.py` with ComposedPatchSet
3. Add filter() and union() operations
4. Add tests for each PatchSet type
5. Update RangePatchSet.filter() to return IndexedPatchSet

**Success criteria:** All PatchSet types working, tested

### Phase 5: Implement Bisect Strategy
**Goal:** Add divide-and-conquer strategy

1. Create `strategies/bisect.py` with BisectStrategy
2. Implement recursive split/test logic
3. Make strategy selectable via config
4. Test with small patch count first
5. Test with full 6439 patches

**Success criteria:** Can bisect to find working patches in O(log n) builds

### Phase 6: Add Metadata and Analysis
**Goal:** Enable smart decisions

1. Add metadata storage to Patch
2. Implement annotate() on all PatchSets
3. Create analyzer functions (parse author, files, dependencies)
4. Add filter-by-metadata capabilities
5. Test author-based filtering ("skip Hank")

**Success criteria:** Can filter patches by metadata

### Phase 7: Compose Strategies
**Goal:** Build smarter combined approaches

1. Create strategy composition framework
2. Implement hybrid: bisect first, sequential for failures
3. Implement look-ahead: try fixing patches with later commits
4. Add configuration for strategy selection

**Success criteria:** Multiple strategies working, composable

## Design Choices

1. **Metadata Storage:** On Patch object directly (mutable dict) - simplest approach
2. **PatchSet Mutability:** Functional (all ops return new PatchSet) - safer, more composable
3. **Test Results:** Binary bool (success/failure)
4. **Strategy Selection:** Config-driven (strategy: "bisect") - flexible
5. **Patch Loading:** Eager (load all upfront) - 6439 patches ~500MB, manageable

### Future Extensions

1. **SQLite Database** (README Level 3)
   - Track all patch attempts (success/failure/reason)
   - Learn patterns over time
   - Skip known-bad patches on future runs

2. **LLM Patch Rewriting** (README Level 5)
   - LazyPatchSet with LLM-generated alternatives
   - Only invoke for high-value failed patches
   - Cache rewrites in database

3. **ML Success Prediction** (README Level 6)
   - Train model on historical data
   - Predict patch success probability
   - Sort patches by predicted success

4. **Parallel Application**
   - Independent patches can be tested in parallel branches
   - Requires dependency analysis
   - Merge successful branches

## Success Metrics

**Phase 1-3:** No regressions, cleaner code
**Phase 4-5:** Can handle 6439 patches in <100 builds (vs 6439 sequential)
**Phase 6-7:** Can filter/reorder intelligently, recover >50% of skipped patches
