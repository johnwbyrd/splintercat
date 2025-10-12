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

You don't want to resolve 50 conflicts and then discover the build is broken. The system uses strategies to decide when to build and test:

- **optimistic**: Resolve everything, then test once (fast but risky)
- **batch**: Resolve 10 conflicts, test, repeat (balanced)
- **per-conflict**: Resolve one conflict, test immediately (slow but safe)

A planner LLM picks the strategy based on the merge size and complexity.

### Step 4: Recover from Failures

When the build breaks, a summarizer LLM reads the build log and extracts what went wrong. Then the planner LLM decides how to fix it:

- **retry-all**: Re-resolve all conflicts with the error message as additional context
- **retry-specific**: Re-resolve just the conflicts that probably caused the error
- **bisect**: Binary search to find the bad resolution
- **switch-strategy**: Change to a more conservative approach (batch → per-conflict)
- **abort**: Give up and ask a human for help

The system tries up to 5 recovery attempts before giving up.

### Step 5: Finish

Once all conflicts are resolved and tests pass, git-imerge simplifies the hundreds of tiny merges into a single clean two-parent merge commit. It looks like a normal merge, preserves all the original commit hashes, and everything works.

## Architecture

### Three LLMs with Different Jobs

**Resolver** (fast, cheap model):
- Input: Conflict with context
- Output: Resolved code
- Model: gpt-4o-mini or similar

**Summarizer** (fast, cheap model):
- Input: Build/test log (may be huge)
- Output: What failed and where
- Model: gpt-4o-mini or similar

**Planner** (smart, expensive model):
- Input: Merge state, failure history
- Output: Strategic decisions with reasoning
- Model: claude-sonnet-4 or similar

### Workflow Orchestration

Pydantic AI Graph manages the workflow as a state machine:
- Routes between resolving conflicts, building, testing, and recovery
- Persists state so you can resume interrupted merges
- Logs every decision for debugging

### Configuration

Everything is configured in config.yaml:
- Which branch to merge
- Build and test commands
- Which LLM models to use
- Strategy preferences and retry limits

You can override any setting via environment variables or command-line arguments.

## Why This Design

### Small, Isolated Changes

git-imerge gives us tiny, isolated conflicts. When something breaks, we know exactly which commits were involved. This makes automated recovery actually possible.

### Multiple LLMs for Multiple Jobs

Resolving conflicts is mechanical work (fast model). Strategic planning requires reasoning (expensive model). Using the right model for each job keeps costs reasonable.

### Incremental Validation

Testing after every resolution would be too slow. Testing only at the end makes failures hard to debug. Letting an LLM decide when to test balances speed and debuggability.

### Intelligent Recovery

Most merge tools just fail when the build breaks. Splintercat analyzes the failure, identifies the likely cause, and tries a different approach. This turns "stuck forever" into "succeeds after 2-3 attempts."

## What This Doesn't Do

- Won't subdivide individual commits (git-imerge limitation)
- Won't ask you for approval at each step (fully automated)
- Won't learn from historical merges (no ML/memory)
- Won't resolve conflicts in parallel (sequential only)
- Won't give you a web UI (command-line only)

These might come later, but they're not in the MVP.

## Success Looks Like

You run `splintercat merge`, go get coffee, and come back to a completed merge with all tests passing. The logs show what the LLMs decided and why. If it failed, the logs explain what went wrong and what recovery strategies were tried.
