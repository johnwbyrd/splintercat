# Splintercat Design

## The Problem

You need to merge a huge upstream branch with hundreds of commits and dozens of conflicts. If you merge it all at once and the build breaks, you have no idea which conflict resolution caused the problem. You're stuck manually bisecting or giving up.

## The Solution

Break the merge into tiny pieces, resolve each conflict automatically with an LLM, and validate incrementally. When something breaks, the system figures out what went wrong and tries again with a different approach.

## How It Works

### Step 1: Subdivide the Merge

Use git-imerge to break your 1000-commit merge into pairwise merges. Instead of merging branch A (1000 commits) into branch B (500 commits) all at once, git-imerge creates a grid of small merges: commit 1 from A with commit 1 from B, then commit 2 from A with commit 1 from B, and so on.

Each conflict is isolated to a specific pair of commits. This makes debugging feasible.

### Step 2: Resolve Conflicts Automatically

When git-imerge hits a conflict, an LLM looks at:
- What changed on our side
- What changed on their side
- The commit messages explaining why
- The surrounding code context

The LLM picks a resolution (ours, theirs, or a custom merge) and explains its reasoning.

### Step 3: Validate Incrementally

BROKEN CODE DOES NOT GET COMMITTED.  If ANY check fails (build, test, etc.), the system must return to the ResolveConflicts node, without committing the changes and plunging forward in the imerge process. No code that fails validation gets committed or merged. Failed checks = return to previous step, no exceptions.

### Step 4: Finish

Once all conflicts are resolved and tests pass, git-imerge simplifies the hundreds of tiny merges into a single clean two-parent merge commit. It looks like a normal merge, preserves all the original commit hashes, and everything works.

## Architecture

### Logging Directory Structure

Splintercat uses a structured logging system organized by individual merge operations:

```
{log_root}/{merge_name}/default/
├── state/                           # Persistent state files (workflow.yaml, config.yaml)
│   ├── workflow.yaml                # Pydantic AI graph state
│   └── config.yaml                  # Config snapshot
├── agents/                          # Per-iteration agent logs
│   ├── 001/                         # Iteration 1
│   │   └── agent.log
│   └── 002/                         # Iteration 2
│       └── agent.log
├── tools/                           # Per-iteration tool calls
│   ├── 001/
│   │   └── calls.log
│   └── 002/
│       └── calls.log
└── resolves/                        # Per-iteration resolve/check
    ├── 001/
    │   ├── resolve.log
    │   └── check.log
    └── 002/
        ├── resolve.log
        └── check.log
```

Where `{log_root}` is `~/.local/state/` (platform-specific user state dir). Each merge operation gets its own directory directly under the log root, allowing clean separation between different merge sessions. The `LogManager` class provides type-safe access to log files, ensuring consistent directory creation and preventing typos in category names. Iteration numbers track resolve-check cycles within each merge.

### One LLM, One Job

**Resolver** (single model):
- Input: Conflict with context, optionally error from previous attempt
- Output: Resolved code
- Model: gpt-4o, claude-sonnet-4, or similar

No separate planner or summarizer models. Keep it simple.

### Workflow Orchestration

Pydantic AI Graph manages the workflow as a state machine:
```
Initialize → ResolveConflicts → Check → [retry or next batch or finalize]
```

**Initialize**: Start git-imerge, create strategy from config
**ResolveConflicts**: Resolve conflicts until strategy says to check
**Check**: Run checks, on failure retry with error context, on success continue or finalize
**Finalize**: Call imerge.finalize() to create merge commit

### Configuration

Everything is configured in config.yaml:
- Which branch to merge
- Which strategy to use (optimistic/batch/per_conflict)
- Build and test commands
- Which LLM model to use

You can override any setting via environment variables or command-line arguments.

## Why This Design

### Small, Isolated Changes

git-imerge gives us tiny, isolated conflicts. When something breaks, we know exactly which batch was involved. This makes automated recovery actually possible.

### One Model for Everything

Using a single capable model for all conflict resolution avoids coordination overhead and keeps costs predictable. If this becomes a bottleneck, we can specialize later based on evidence.

### Deterministic Strategy Selection

The user chooses the strategy based on their merge size and risk tolerance. No need for an LLM to make this decision—it's a straightforward engineering tradeoff.

### Simple Retry

Most build failures are due to incorrect conflict resolution. Passing the error log back to the resolver on retry gives it the context to fix the mistake. This is simpler than trying to identify which specific conflict caused the problem.

## What This Doesn't Do

- Won't subdivide individual commits (git-imerge limitation)
- Won't automatically choose strategies (user configured)
- Won't analyze build logs separately (passes raw logs to resolver)
- Won't bisect failures (retries entire batch)
- Won't learn from historical merges (no ML/memory)

These might come later if evidence shows they're needed, but they're not in the MVP.

## Success Looks Like

You run `splintercat merge`, go get coffee, and come back to a completed merge with all tests passing. The logs show what the resolver decided and why. If it failed after max_retries, the logs explain what went wrong and which conflicts to review manually.

## Deferred Complexity

The following were removed as speculative:
- **Planner LLM**: User configures strategy explicitly
- **Summarizer LLM**: Raw error logs work for now
- **Complex recovery**: Bisect, switch-strategy, retry-specific—add only if simple retry fails
- **Multiple check levels**: One check command is enough to start

Add these back only when real-world use shows they're necessary.
