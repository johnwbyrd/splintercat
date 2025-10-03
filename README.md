# splintercat

## What This Does

Maintains a "stable" git branch by continuously trying to apply patches from an upstream branch, testing each one, and keeping only those that pass tests.

If you're tired of upstream breaking your build, this creates a branch that's guaranteed to compile and pass tests.

"The method used by the splinter cat is simple and effective. It climbs one tree, and from the uppermost branches bounds down and across toward the tree it wishes to destroy. Striking squarely with its hard face, the splinter cat passes right on, leaving the tree broken and shattered as though struck by lightning or snapped off by the wind." -William T. Cox, "Fearsome Creatures of the Lumberwoods"

## How It Works

1. Fetches patches from upstream using `git format-patch`
2. Optimistically tries to apply all patches at once
3. If that fails, subdivides and tries smaller batches
4. Runs your test suite after each application
5. Keeps patches that pass tests, rolls back on failure
6. Repeats until all applicable patches are found

Your stable branch only ever contains code that built and tested successfully, with original commit authorship preserved via `git am`.

## Installation

```bash
pip install pydantic pydantic-settings loguru
```

Python 3.11+ required.

## Configuration

Create `config.yaml`:

```yaml
source:
  repo: https://github.com/llvm/llvm-project.git
  branch: main
  path: /path/to/source/repo

target:
  path: /path/to/target/repo
  branch: stable

test_command: ninja check-all

strategy:
  type: sequential

verbose: false
```

Configuration can be overridden via environment variables (e.g., `SPLINTERCAT__SOURCE__REPO=...`) or command-line arguments (e.g., `--source.repo=...`).

## Usage

```bash
python main.py
```

It will:
- Fetch all new patches from upstream since merge-base
- Try applying all patches at once first (optimistic)
- If that fails, subdivide and find working subsets
- Log all operations to console and `splintercat.log`
- Leave you with an updated stable branch containing only passing patches

Run it on a schedule (cron, GitHub Actions, whatever) to keep stable up to date.

See [doc/DESIGN.md](doc/DESIGN.md) for architecture details and design philosophy.

## Why This Exists

Some upstream repositories (looking at you, LLVM) break frequently. If you just track HEAD, you'll spend half your time debugging broken builds.

This automates the tedious process of cherry-picking only the commits that work, giving you a stable branch that others can depend on.
