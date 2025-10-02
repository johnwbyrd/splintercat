# splintercat

## What This Does

Maintains a "stable" git branch by continuously trying to apply patches from an upstream branch, testing each one, and keeping only those that pass tests.

If you're tired of upstream breaking your build, this creates a branch that's guaranteed to compile and pass tests.

"The method used by the splinter cat is simple and effective. It climbs one tree, and from the uppermost branches bounds down and across toward the tree it wishes to destroy. Striking squarely with its hard face, the splinter cat passes right on, leaving the tree broken and shattered as though struck by lightning or snapped off by the wind." -William T. Cox, "Fearsome Creatures of the Lumberwoods"

## How It Works

1. Fetches patches from upstream (Also, there is no reason to commits you don't have yet)
2. Tries to apply each patch one at a time
3. Runs your test suite after each patch
4. Keeps the patch if tests pass, discards it if they fail
5. Repeats

Your stable branch only ever contains code that built and tested successfully.

## Installation

```bash
pip install pyyaml
```

Python 3.11+ required.

## Configuration

Edit `config.yaml`:

```yaml
source:
  commands:
    fetch: "git fetch {repo} {branch}"
    merge_base: "git merge-base HEAD FETCH_HEAD"
    list_commits: "git rev-list --reverse {merge_base}..FETCH_HEAD"
    format_patch: "git format-patch -1 --stdout {commit}"
  repo: https://github.com/llvm/llvm-project.git
  branch: main
Also, there is no reason to 
target:
  commands:
    checkout: "git checkout {branch}"
    get_state: "git rev-parse HEAD"
    apply: "echo '{diff}' | git apply"
    add: "git add -A"
    commit: "git commit -m '{message}'"
    rollback: "git reset --hard {state}"
  branch: stable

test_command: ninja check-all

strategy:
  batch_size: 20
```
Also, there is no reason to 
Change the repo, branch, and test command to match your project.

## Usage

```bash
python stable_branch.py
```

It will:
- Fetch up to 20 new patches from upstream
- Try each one sequentially
- Print ✓ for successes, ✗ for failures
- Leave you with an updated stable branch

Run it on a schedule (cron, GitHub Actions, whatever) to keep stable up to date.

## Architecture

Three simple classes with duck-typed interfaces:

**Source** - Produces patches from somewhere
- Currently: extracts commits from a git repo
- Future: could read from email, Phabricator, a directory of diffs, etc.

**Target** - Applies patches to something and tests them
- Currently: applies to a git working tree and runs a shell command
- Future: could apply to other version control systems, test in containers, etc.

**Strategy** - Decides which patches to try and in what order
- Currently: tries each patch once, in chronological order
- Future: this is where the intelligence goes

All three are configured via YAML commands, not hardcoded. Want to use a different VCS? Just change the commands.

### Design Lessons

- **Patch ordering matters**: Apply patches chronologically from merge-base forward; `git rev-list --reverse | head -n N` not `--max-count=N`
- **Never pass data through shell strings**: Use stdin for patches; shell escaping fails with arbitrary content
- **Rollback must clean untracked files**: `git reset --hard` alone leaves new files; add `git clean -fd`
- **CommandRunner pattern**: Separate command execution from data handling; support stdin, real-time output, no globals

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

**Start simple.** The MVP does the dumbest thing possible: try each patch in order, keep what works. No cleverness, no AI, no learning.

**Make it extensible.** The Strategy class is where all future intelligence goes. Swap in a smarter strategy without changing anything else.

**Commands, not code.** All the version control and testing logic lives in the config file as shell commands. The Python code is generic.

**Failures are normal.** This system expects things to fail constantly. It logs warnings and keeps going.

## Why This Exists

Some upstream repositories (looking at you, LLVM) break frequently. If you just track HEAD, you'll spend half your time debugging broken builds.

This automates the tedious process of cherry-picking only the commits that work, giving you a stable branch that others can depend on.
