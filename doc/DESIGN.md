# Splintercat Design

## Architecture

Four main components with typed interfaces (ABC):

**Source** - Produces patches from somewhere
- Currently: `GitSource` extracts commits from a git repo using `git format-patch`
- Future: could read from email, Phabricator, a directory of diffs, etc.

**Target** - Applies patches to something and tests them
- Currently: `GitTarget` uses `git am` to preserve authorship, runs test command
- Future: could apply to other VCS, test in containers, etc.

**Strategy** - Pure function that decides which patches to try next based on history
- Input: `State` (complete history of all attempts)
- Output: `PatchSet` to try next, or `None` if done
- Currently: `SequentialStrategy` tries all first, then subdivides on failure
- Future: `BisectStrategy`, ML-based prediction, etc.

**Runner** - Orchestrates the main loop
- Fetches patches from Source
- Maintains State with complete attempt history
- Calls Strategy to decide what to try next
- Uses Target to apply and test

All components use Pydantic models for type-safe configuration and state management.

## Design Lessons

- **Patch ordering matters**: Apply patches chronologically from merge-base forward
- **Use git am not git apply**: Preserves original commit authorship
- **Never pass data through shell strings**: Use stdin for patches; shell escaping fails with arbitrary content
- **Strategy is pure function**: Receives State, returns PatchSet; no internal state
- **Optimistic first**: Always try all patches before subdividing
- **Log everything**: Real-time streaming via loguru for later analysis

## Future Improvements

### Level 2: Bisection Strategy

When applying all patches at once fails, bisect to find which subset works. Much faster than trying one at a time.

### Level 3: Memory

Add SQLite database to remember:
- Which patches have failed before
- How many times each patch has been attempted
- Success rates by author, time of day, file paths touched, etc.

Use this history to skip known-bad patches or reorder attempts.

### Level 4: Smart Ordering

Don't just try patches chronologically. Use history to predict which patches are likely to succeed and try those first.

Heuristics might include:
- Patches from reliable authors
- Patches that touch stable areas of the codebase
- Patches that historically work well together

### Level 5: Patch Rewriting

When a patch fails to apply, use an LLM to adapt it to the current codebase. Generate a new patch and try that instead.

### Level 6: Learning

Train a model on historical success/failure data. Predict probability of success for each patch. Optimize for maximum patches applied per test run.

## Design Philosophy

**Start simple.** The MVP does the dumbest thing possible: try patches optimistically, subdivide on failure. No cleverness beyond that.

**Make it extensible.** The Strategy abstraction is where all future intelligence goes. Swap in a smarter strategy without changing anything else.

**Type safety.** Pydantic models for configuration and state. ABC for interfaces. Let the type checker catch bugs.

**Failures are normal.** This system expects things to fail constantly. It logs everything and keeps going.
