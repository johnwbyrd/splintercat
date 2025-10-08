# Splintercat Code Layout

This document describes the file structure and organization of the splintercat codebase.

## Directory Structure

### src/state/

Pydantic models for LangGraph state management. These models define the data structures that flow through the workflow state machine and are serialized for resume capability.

- `__init__.py` - Export all state models
- `workflow.py` - MergeWorkflowState (main LangGraph state container)
- `conflict.py` - ConflictInfo, ConflictResolution (conflict tracking and resolution data)
- `attempt.py` - MergeAttempt (history of each merge attempt with results)
- `build.py` - BuildResult (build/test execution results)

### src/model/

LLM model wrappers. Three distinct model roles with different responsibilities and different underlying LLM models (configured separately for cost/performance tradeoffs).

- `__init__.py` - Export all model classes
- `resolver.py` - Conflict resolver model (cheap/fast model, resolves merge conflicts mechanically)
- `summarizer.py` - Build log summarizer model (cheap/fast model, extracts error info from verbose logs)
- `planner.py` - Strategic planner model (smart/expensive model, makes all strategic and tactical decisions)

### src/workflow/nodes/

Individual workflow nodes for the LangGraph state machine. Each node is a pure function that takes state and returns updated state.

- `__init__.py` - Export all node functions
- `initialize.py` - Initialize node: Start git-imerge, set up initial state
- `plan_strategy.py` - PlanStrategy node: Planner chooses initial merge strategy and parameters
- `resolve_conflicts.py` - ResolveConflicts node: Resolve conflicts using resolver model (handles batch/single, with optional failure context)
- `build_test.py` - BuildTest node: Run build/test command, capture output to log file
- `summarize_failure.py` - SummarizeFailure node: Extract error information from failed build logs
- `plan_recovery.py` - PlanRecovery node: Planner analyzes failure and returns routing decision
- `finalize.py` - Finalize node: Simplify merge to single commit, clean up git-imerge state

### src/workflow/

LangGraph state machine definition and routing logic.

- `__init__.py` - Export graph
- `graph.py` - LangGraph state machine (creates graph, defines nodes and edges, implements routing logic)

Routing logic in graph.py:
- BuildTest result: success → Finalize, failure → SummarizeFailure
- PlanRecovery decision routing:
  - retry (retry-all or retry-specific) → ResolveConflicts with failure context
  - bisect → BuildTest with resolution subset
  - switch-strategy → PlanStrategy
  - abort → END

### src/git/

Git operations and git-imerge integration.

- `__init__.py` - Export imerge wrapper
- `imerge.py` - Wrapper around git-imerge library (start merge, get conflicts, get frontier, finalize to single commit)

### src/runner/

Build and test execution with log management.

- `__init__.py` - Export BuildRunner
- `build.py` - Execute build/test commands, save logs to timestamped files in .splintercat/build-logs/

### src/core/

Core infrastructure (command execution, configuration, logging, results).

- `__init__.py` - Core functionality exports
- `command_runner.py` - Execute shell commands with stdin, real-time output, interactive mode
- `config.py` - Configuration loading from YAML, environment variables, CLI arguments (Pydantic Settings)
- `log.py` - Logging setup and utilities (loguru)
- `result.py` - Result value objects (command execution results)

Configuration updates needed in config.py:
- Add BuildTestConfig class (command, output_dir, timeout)
- Add LLMConfig class (api_key, base_url, resolver_model, summarizer_model, planner_model)
- Add build_test and llm fields to Settings model

### src/defaults/

Default configuration values.

- `commands.yaml` - Default command templates for git operations

### Entry Point

- `main.py` - Application entry point (initialize Settings, setup logging, create and run LangGraph workflow)

### Tests

- `tests/__init__.py` - Test suite package

### Documentation

- `doc/DESIGN.md` - Complete architecture and design specification (source of truth)
- `doc/LAYOUT.md` - This file (code organization and file structure)
- `doc/LLM.md` - Instructions for LLM assistants working on this codebase
- `doc/gitimerge.py` - Reference copy of git-imerge source for understanding the library
- `README.md` - Project overview and usage

## Workflow Node Flow

### Happy Path (No Build Failures)

```
Initialize
  ↓
PlanStrategy
  ↓
ResolveConflicts
  ↓
BuildTest (success)
  ↓
Finalize
```

### Failure Recovery Path

```
Initialize
  ↓
PlanStrategy
  ↓
ResolveConflicts
  ↓
BuildTest (failure)
  ↓
SummarizeFailure
  ↓
PlanRecovery
  ↓
[Routes based on recovery decision:]
  - retry → ResolveConflicts (with failure context)
  - bisect → BuildTest (with resolution subset)
  - switch-strategy → PlanStrategy
  - abort → END
```

## Design Principles

- Configuration-driven: Settings in config.yaml, not hardcoded
- State persistence: Pydantic models serializable for resume capability
- Separation of concerns: Models, nodes, state, git ops, build ops all separate
- Nodes as pure functions: Take state, return updated state
- LangGraph handles routing: Based on state values and node return values
- No recovery execution node: Recovery actions are parameters to existing nodes, not separate execution
