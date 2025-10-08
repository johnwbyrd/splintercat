# splintercat

## What This Does

LLM-assisted git merge conflict resolution with build/test validation and intelligent recovery strategies.

Splintercat automates merging large upstream branches by:
- Using git-imerge to subdivide merges into manageable pairwise commits
- Resolving conflicts automatically with LLMs
- Validating each resolution with build/test
- Adapting merge strategy based on build results
- Recovering intelligently from failures

The result is a single clean merge commit that preserves all original commit hashes and passes all tests.

## Project Status

**Current Phase**: Design complete, implementation pending

The architecture is designed and documented in [doc/design.md](doc/design.md). Implementation will begin when we encounter real-world merge scenarios that simpler tools cannot handle.

## Design Philosophy

From "Fearsome Creatures of the Lumberwoods" by William T. Cox:

> "The method used by the splinter cat is simple and effective. It climbs one tree, and from the uppermost branches bounds down and across toward the tree it wishes to destroy. Striking squarely with its hard face, the splinter cat passes right on, leaving the tree broken and shattered as though struck by lightning or snapped off by the wind."

Splintercat takes large, complex merges and breaks them into small, manageable pieces that can be resolved and validated independently.

## Architecture Overview

### Components

- **git-imerge**: Subdivides large merges into pairwise commit merges, isolates conflicts efficiently
- **LangGraph**: Orchestrates workflow, manages state machine, enables resume capability
- **LLMs** (three roles):
  - Conflict Resolver: Resolves merge conflicts automatically
  - Build Summarizer: Extracts failure information from build logs
  - Strategic Planner: Makes decisions about merge strategy and recovery
- **Existing infrastructure**: CommandRunner, Pydantic Settings, loguru logging

### Merge Strategies

- **optimistic**: Resolve all conflicts first, test once (fastest)
- **batch**: Resolve N conflicts, test, repeat (balanced)
- **per-conflict**: Resolve one conflict, test, repeat (safest)

Strategy is chosen by the Planner LLM based on merge characteristics.

### Recovery on Build Failure

When builds fail, the Planner LLM analyzes the failure and chooses:
- **retry-all**: Re-resolve all conflicts with failure context
- **retry-specific**: Re-resolve only the conflicts that likely caused failure
- **bisect**: Binary search to find problematic resolution
- **switch-strategy**: Change to more conservative approach
- **abort**: Report to human for manual intervention

## Configuration

Configuration is in `config.yaml`. See the file itself for complete documentation with inline comments.

Key configuration areas:
- **source**: What to merge from (git ref)
- **target**: Where to merge to (workdir, branch)
- **build_test**: Validation command, timeout, log storage
- **llm**: API key, model selection (resolver, summarizer, planner)
- **imerge**: git-imerge settings
- **merge**: Strategy options, retry limits

Configuration can be overridden via environment variables (e.g., `SPLINTERCAT__LLM__API_KEY=...`) or command-line arguments (e.g., `--llm.planner_model=...`).

## Installation

```bash
pip install -r requirements.txt
```

Python 3.11+ required.

Dependencies:
- loguru (logging)
- pydantic, pydantic-settings (configuration)
- langchain, langchain-openai (LLM orchestration)
- langgraph (workflow state machine)
- git-imerge (merge subdivision)

## Usage

(To be implemented)

```bash
export OPENROUTER_API_KEY=your-key-here
python main.py
```

The workflow will:
1. Initialize git-imerge merge
2. Planner chooses merge strategy
3. Resolve conflicts with LLM
4. Validate with build/test
5. On failure: analyze, recover, retry
6. Produce final single merge commit

All decisions and actions are logged to console and `splintercat.log`.

## Documentation

- [doc/design.md](doc/design.md) - Complete architecture and design
- [doc/llm.md](doc/llm.md) - Instructions for LLM assistants working on this codebase
- [doc/merge-resolver.md](doc/merge-resolver.md) - Tool-based conflict resolution architecture
- [doc/gitimerge.py](doc/gitimerge.py) - Reference copy of git-imerge source for understanding the library

## Development

See [doc/llm.md](doc/llm.md) for development guidelines.

Key points:
- Virtual environment: `source ../.venv/bin/activate`
- No emojis anywhere
- No code blocks in markdown documentation
- design.md is the source of truth for architecture
- Don't implement until needed for real-world merge cases

## Why This Exists

Large upstream repositories (like LLVM) require frequent merging of thousands of commits. Manual conflict resolution is tedious and error-prone. Build failures may indicate incorrect conflict resolutions, requiring careful analysis and retry.

Splintercat automates this process while maintaining the ability to recover intelligently from failures, producing a clean merge that preserves history and passes all tests.