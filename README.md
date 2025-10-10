# splintercat

Merging a thousand upstream commits by hand is miserable. Resolving dozens of conflicts is tedious.

Discovering your merge breaks the build hours later is worse. Now you have no idea which conflict resolution caused the problem.

Splintercat automates the entire process. It breaks large merges into manageable pieces using git-imerge, resolves conflicts automatically with LLMs, validates each batch with your build and test suite, and recovers intelligently when something goes wrong.

You get a clean merge commit that preserves history and passes all tests.

## How it works

Splintercat uses git-imerge to subdivide your merge into small pairwise commits. Each conflict gets resolved by an LLM that understands the code context and commit messages.

The system validates incrementally—testing after small batches of resolutions rather than waiting until the end.

When builds fail, it analyzes the errors and tries different resolution strategies automatically. Most merges succeed without human intervention.

The result is a single two-parent merge commit, just like a normal merge, with all original commit hashes preserved.

## Why "splintercat"?

From "Fearsome Creatures of the Lumberwoods" by William T. Cox:

> "The method used by the splinter cat is simple and effective. It climbs one tree, and from the uppermost branches bounds down and across toward the tree it wishes to destroy. Striking squarely with its hard face, the splinter cat passes right on, leaving the tree broken and shattered as though struck by lightning or snapped off by the wind."

Large merges get broken into small, manageable pieces.

## Installation

Requires Python 3.12 or later.

```bash
pip install -e .
```

## Quick start

Create a `config.yaml` file:

```yaml
config:
  git:
    source_ref: upstream/main
    target_workdir: /path/to/your/repo
    target_branch: your-branch
    imerge_name: upstream-merge

  build:
    command: make test
    output_dir: .splintercat/logs

  llm:
    api_key: ${OPENROUTER_API_KEY}
    base_url: https://openrouter.ai/api/v1
    resolver_model: openai/gpt-4o-mini
    planner_model: anthropic/claude-sonnet-4
```

Set your API key:

```bash
export OPENROUTER_API_KEY=your-key-here
```

Run the merge:

```bash
python main.py merge
```

The system will resolve conflicts, run your tests, and handle failures automatically. Check `splintercat.log` for detailed progress.

## Configuration

The `config.yaml` file controls everything.

Key settings:

- `config.git.source_ref`: What branch to merge from
- `config.git.target_branch`: What branch to merge into
- `config.build.command`: Your build/test command
- `config.llm.api_key`: OpenRouter or OpenAI API key
- `config.llm.resolver_model`: Fast, cheap model for conflict resolution
- `config.llm.planner_model`: Smart model for strategy decisions

You can override any setting via environment variables (use `SPLINTERCAT__CONFIG__GIT__SOURCE_REF` format) or command-line arguments (`--config.git.source_ref=value`).

## Current status

Core architecture is complete. LLM integration and workflow nodes are still being implemented.

See [doc/todo.md](doc/todo.md) for implementation status.

## Documentation

- [doc/design.md](doc/design.md) - Architecture and design rationale
- [doc/todo.md](doc/todo.md) - Implementation roadmap
- [doc/merge-resolver.md](doc/merge-resolver.md) - How conflict resolution works
- [doc/llm.md](doc/llm.md) - Guidelines for contributors

## Why this exists

Large projects like LLVM require frequent merges of thousands of upstream commits.

Doing this manually is slow and error-prone. When builds fail after merging, isolating the problematic conflict resolution is nearly impossible with traditional tools.

Splintercat automates the entire workflow while maintaining the ability to recover from failures intelligently.
