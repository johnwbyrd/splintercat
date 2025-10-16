# Merge Benchmark Specification

## Overview

A benchmark system for evaluating merge tools based on functional correctness rather than textual similarity. Success is defined as: merged code passes specified check command.

## Purpose

Measure whether merge tools produce working software. Check commands validate functional correctness (compilation, tests, etc.). Textual comparison to ground truth is explicitly not performed.

## YAML Schema

```yaml
benchmark:
  name: string             # Unique identifier for this benchmark

  source:
    repo: string          # Git URL (https or file path)
    ref: string           # Branch, tag, or commit SHA
    commit: string        # Optional: pin to specific commit

  target:
    repo: string          # Git URL (can be same as source)
    ref: string           # Branch, tag, or commit SHA
    commit: string        # Optional: pin to specific commit

  check:
    command: string       # Shell command to execute
    timeout: integer      # Maximum execution time in seconds
    workdir: string       # Working directory (default: ".")

  success:
    required: boolean     # Must check pass for benchmark success?
```

### Field Requirements

**Required fields**: `name`, `source.repo`, `source.ref`, `target.repo`, `target.ref`, `check.command`, `check.timeout`, `success.required`

**Optional fields**: `source.commit`, `target.commit`, `check.workdir`

### Field Constraints

- `name`: Must be unique across benchmark suite
- `repo`: Must be valid git URL or local path
- `ref`: Must exist in repository
- `commit`: If specified, must be reachable from `ref`
- `command`: Arbitrary shell command
- `timeout`: Positive integer
- `workdir`: Relative path from repository root
- `required`: Currently must be `true` (for future extension)

## Execution Model

### Setup Phase

1. Clone `source.repo` at `source.ref`
2. If `source.commit` specified, checkout that commit
3. Clone `target.repo` at `target.ref`
4. If `target.commit` specified, checkout that commit

### Merge Phase

Implementation-defined. Merge tool attempts to merge source into target. On success, produces merged git tree.

### Validation Phase

1. Change directory to `check.workdir`
2. Execute `check.command` in shell
3. Wait up to `check.timeout` seconds
4. Capture exit code

### Result Determination

**Success**: Exit code = 0 and execution time < timeout

**Failure**: Exit code ≠ 0 or timeout exceeded

## Valid Benchmark Scenarios

### Standard Merge

Source and target are different branches, both branches pass checks independently, merge must also pass.

### Upstream Sync

Source is upstream repository, target is fork, many commits and conflicts expected.

### Broken Tree Recovery

Source or target (or both) fail checks independently. Merged result must pass.

**Note**: This scenario is valid and important. Both branches can be broken during development, but correct merge produces working code. This happens frequently in practice when conflicting refactorings occur on both branches.

## pytest Integration

### File Organization

```
benchmarks/
  llvm-mos-merge.yaml
  example-simple.yaml
  ...

tests/
  test_benchmarks.py
```

### Test Generation

Each `benchmarks/*.yaml` file generates one pytest test case. Test function:
1. Loads YAML
2. Clones repositories
3. Invokes merge tool
4. Executes check command
5. Asserts success

### Test Naming

Test name derived from `benchmark.name` field. Example: `test_benchmark_llvm_mos_merge`.

## Implementation Requirements

### Must Implement

- YAML parsing and validation
- Git repository cloning
- Checkout of specified refs/commits
- Shell command execution with timeout
- Exit code capture
- pytest test case generation

### Need Not Implement (For Now)

- Reproducibility enforcement (user must have dependencies)
- Multiple checks (only one `check:` per benchmark)
- Cost tracking (tokens, time, dollars)
- Result publishing (pushing merged tree)
- Parallel execution (run benchmarks sequentially)

## Example Benchmark

```yaml
benchmark:
  name: "llvm-mos-heaven-merge-2024-12"

  source:
    repo: "https://github.com/llvm/llvm-project.git"
    ref: "main"
    commit: "a1b2c3d4e5f6"

  target:
    repo: "https://github.com/llvm-mos/llvm-mos.git"
    ref: "stable"
    commit: "1a2b3c4d5e6f"

  check:
    command: "ninja check-llvm"
    timeout: 3600
    workdir: "build"

  success:
    required: true
```

**Execution**: Merge llvm main into llvm-mos stable, run `ninja check-llvm` in `build/` directory, must complete within 3600 seconds with exit code 0.

## Non-Goals

### Not Measuring

- Textual similarity to human resolution
- Code quality or style
- Performance characteristics
- Semantic correctness beyond tests

### Not Providing

- Docker containers (user has dependencies)
- Build system setup (user runs setup first)
- Environment isolation (runs on user's machine)
- Deterministic reproducibility (future concern)

## Success Criterion

A merge tool passes a benchmark if and only if the merged tree passes the check command (exit code 0 within timeout).

How the tool produces the merged tree is irrelevant. Multiple different merged trees can all pass the same benchmark. This is intentional and correct.

## Future Extensions

Deferred until needed:

- Multiple check commands with different requirements
- Optional vs required checks
- Cost tracking and reporting
- Result publishing to public repository
- Docker-based reproducibility
- Benchmark difficulty classification
- Continuous benchmarking in CI

Current specification intentionally minimal to enable rapid implementation.
