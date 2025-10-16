# splintercat

Merging a thousand upstream commits by hand is miserable. Resolving dozens of conflicts is tedious.

Discovering your merge breaks the build hours later is worse. Now you have no idea which conflict resolution caused the problem.

Splintercat automates the entire process. It breaks large merges into manageable pieces using git-imerge, resolves conflicts automatically with an LLM, and validates incrementally with your build and test suite.

You get a clean merge commit that preserves history and passes all tests.

## How it works

Splintercat uses git-imerge to subdivide your merge into small pairwise commits. Each conflict gets resolved by an LLM that understands the code context and commit messages.

The system validates incrementally—testing after small batches of resolutions rather than waiting until the end.

When builds fail, it retries the current batch with error context so the LLM can make better decisions. After a configurable number of retries, it stops and asks for human help.

The result is a single two-parent merge commit, just like a normal merge, with all original commit hashes preserved.

## Why "splintercat"?

From "Fearsome Creatures of the Lumberwoods" by William T. Cox:

> "The method used by the splinter cat is simple and effective. It climbs one tree, and from the uppermost branches bounds down and across toward the tree it wishes to destroy. Striking squarely with its hard face, the splinter cat passes right on, leaving the tree broken and shattered as though struck by lightning or snapped off by the wind."

Large merges get broken into small, manageable pieces.

## Installation

Requires Python 3.11 or later.

```bash
pip install -e .
```

After installation, the `splintercat` command will be available in your PATH.

## Quick start

Create a `splintercat.yaml` file in your project directory:

```yaml
config:
  git:
    source_ref: upstream/main
    target_workdir: /path/to/your/repo
    target_branch: your-branch
    imerge_name: upstream-merge

  check:
    commands:
      quick: make test
    output_dir: .splintercat/logs

  llm:
    base_url: https://openrouter.ai/api/v1
    model: openai/gpt-4o

  strategy:
    name: batch
    batch_size: 10
    max_retries: 3
```

Create a `.env` file for your API key.  See https://ai.pydantic.dev/models/openai/ for a list of supported providers and required API key environment variable names:

```
YOURPROVIDER_API_KEY=your-key-here
```

Run the merge:

```bash
splintercat merge
```

The system will resolve conflicts, run your tests, and handle failures automatically. Check `splintercat.log` for detailed progress.

## Configuration

Splintercat loads configuration from multiple locations:

1. **Package defaults** - Built-in sensible defaults
2. **User config** - Your personal settings (LLM models, preferences)
   - Linux: `~/.config/splintercat/splintercat.yaml`
   - macOS: `~/Library/Application Support/splintercat/splintercat.yaml`
   - Windows: `%LOCALAPPDATA%\splintercat\splintercat.yaml`
3. **Project config** - Project-specific settings (`./splintercat.yaml`)
4. **Environment variables** - Secrets and overrides (`SPLINTERCAT_CONFIG__SECTION__KEY`)
5. **CLI arguments** - One-off changes (`--config.git.source_ref=value`)

Key settings:

- `config.git.source_ref`: What branch to merge from
- `config.git.target_branch`: What branch to merge into
- `config.check.commands`: Your build/test commands
- `config.llm.model`: LLM model for conflict resolution (e.g., openai/gpt-4o)
- `config.strategy.name`: Strategy (optimistic, batch, or per_conflict)
- `config.strategy.batch_size`: How many conflicts to resolve before checking

See [docs/configuration.md](docs/configuration.md) for complete details.

## Current status

MVP architecture complete: simplified workflow with 4 nodes (Initialize, ResolveConflicts, Check, Finalize), single LLM model, and simple retry mechanism. Resolver implementation in progress.

See [docs/todo.md](docs/todo.md) for implementation roadmap.

## Using as a Library

Splintercat can also be used as a Python library:

```python
from splintercat.command import MergeCommand
from splintercat.core import State

# Load configuration
state = State()

# Run merge programmatically
await MergeCommand().run_workflow(state)
```

## Documentation

- [docs/design.md](docs/design.md) - Architecture and design rationale
- [docs/todo.md](docs/todo.md) - Implementation roadmap
- [docs/merge-resolver.md](docs/merge-resolver.md) - How conflict resolution works
- [docs/llm.md](docs/llm.md) - Guidelines for contributors

## Why this exists

Large projects like LLVM require frequent merges of thousands of upstream commits.

Doing this manually is slow and error-prone. When builds fail after merging, isolating the problematic conflict resolution is nearly impossible with traditional tools.

Splintercat automates the entire workflow with a focused, pragmatic approach: subdivide the merge, resolve conflicts with LLM assistance, validate incrementally, and retry with error context when needed.
