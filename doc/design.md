# Splintercat Design - LLM-Assisted Git Merge

## Overview

Splintercat is an automated git merge conflict resolution system using LLMs, with build/test validation and intelligent recovery strategies. It subdivides large merges into manageable pieces, resolves conflicts automatically, validates each resolution through builds and tests, and adapts its strategy based on results.

## Problem Statement

Merging large upstream branches presents several challenges:
- Hundreds or thousands of commits with many conflicts
- Each conflict resolution must be validated with build/test
- Manual resolution is tedious and error-prone
- Build failures may indicate incorrect conflict resolutions
- Need to isolate which resolutions caused failures

Traditional approaches either merge everything at once (hard to debug failures) or require extensive manual intervention.

## Solution Approach

Use git-imerge to subdivide merges into pairwise commit merges, employ LLMs for conflict resolution and strategic planning, orchestrate the workflow with Pydantic AI's pydantic-graph, and validate resolutions with build/test at strategic points chosen by an LLM planner.

## Architecture Components

### git-imerge (Python Library)

**Purpose**: Merge subdivision and conflict detection engine

**How it works**:
- Uses bisection algorithm to find minimal conflict units
- Breaks large merges into pairwise commit merges (commit A from branch 1, commit B from branch 2)
- Tracks merge state in git refs under `refs/imerge/NAME/`
- Maintains frontier of mergeable vs. conflicting commit pairs

**Key features**:
- Incremental and resumable
- Efficient conflict isolation through bisection
- State persisted in git repository
- Final simplification produces single clean merge commit

**Key limitation**: Commits are atomic units - cannot subdivide individual commits further

**Output**: Single two-parent merge commit preserving original commit hashes from both branches

### Pydantic AI Graph (Orchestration)

**Purpose**: State machine managing the merge workflow

**Responsibilities**:
- Routes between git-imerge, LLMs, and build/test
- Maintains workflow state for resume capability
- Decision routing based on Planner LLM output
- Handles interruption and continuation

**State persistence**: Pydantic models serialized to allow resuming interrupted merges

### LLM Roles (Three Models)

#### 1. Conflict Resolver (cheap/fast model)

**Input**:
- File path with conflict markers
- Surrounding code context
- Commit messages from both sides
- (On retry) Previous failure context

**Output**:
- Resolved file content only
- No explanations or markdown formatting

**Model**: `openai/gpt-4o-mini` or similar fast model

**Prompt approach**: Direct and minimal - provide conflict, request resolution

#### 2. Build Summarizer (cheap/fast model)

**Input**:
- Path to build/test log file (potentially large)

**Output** (structured):
- Error type: `compile_error` | `link_error` | `test_failure` | `timeout`
- Location: file:line (if applicable)
- Root cause: one-sentence description
- Relevant excerpt: actual error message(s)

**Handles**: Both compilation errors and test failures

**Model**: `openai/gpt-4o-mini` or similar

**Purpose**: Extract actionable information from verbose build logs, filtering noise to find root causes

#### 3. Strategic Planner (smart/expensive model)

**Input**:
- Current merge state
- Previous attempts and their outcomes
- Available strategy options
- Build failure summaries

**Output**:
- Strategic decisions with reasoning
- Specific actions to take
- When to change strategies
- When to abort

**Responsibilities**:

1. **Initial strategy selection**
   - Analyze merge scope (commit count, affected subsystems)
   - Choose: optimistic | batch | per-conflict
   - Set parameters (batch size, etc.)

2. **Failure recovery**
   - Analyze what failed and why
   - Choose recovery strategy:
     - retry-all: re-resolve all conflicts with failure context
     - retry-specific: identify and re-resolve specific conflicts
     - bisect: binary search for problematic resolution
     - switch-strategy: change to more conservative approach
     - abort: report to human
   - Specify which conflicts to focus on

3. **Strategic adaptation**
   - Detect patterns in failures
   - Adjust approach dynamically
   - Determine when problem is beyond automated recovery

**Model**: `anthropic/claude-sonnet-4` or similar reasoning-capable model

### Existing Infrastructure

#### CommandRunner
- Execute git commands
- Run build/test commands with output capture
- Real-time output streaming
- Already implemented in `src/core/command_runner.py`

#### Pydantic Settings
- Configuration loading from YAML, environment variables, and CLI arguments
- Type-safe configuration with validation
- State serialization for resume capability
- Already implemented in `src/core/config.py`

#### loguru Logger
- Console and file logging with rotation
- Captures all LLM interactions, decisions, and build results
- DEBUG level to files, INFO level to console
- Already implemented in `src/core/log.py`

## Workflow

### High-Level Flow

```
Initialize git-imerge merge
  ↓
Planner chooses initial strategy
  ↓
Execute strategy:
  - optimistic: resolve all conflicts, then test once
  - batch: resolve N conflicts, test, repeat
  - per-conflict: resolve one conflict, test, repeat
  ↓
Build/Test (save output to log file)
  ↓
Success? ──YES──> Finalize merge (simplify to single commit)
  ↓
  NO
  ↓
Summarizer extracts error information from log
  ↓
Planner analyzes failure and decides recovery approach
  ↓
Execute recovery plan
  ↓
Repeat until success or max_retries exceeded or Planner aborts
```

### Detailed State Machine

**Nodes** (to be refined during implementation):
- **Initialize**: Start git-imerge, set up state
- **PlanStrategy**: Planner chooses initial approach
- **ResolveConflicts**: Execute conflict resolution (batch or single)
- **BuildTest**: Run build/test command, capture output
- **SummarizeBuildFailure**: Extract error information from logs
- **PlanRecovery**: Planner analyzes and decides next steps
- **ExecuteRecovery**: Apply recovery plan
- **Finalize**: Simplify to single merge commit, clean up

**Edges**: Determined dynamically based on Planner decisions and build results

**State**: Pydantic models tracking current position, history, and decisions

## Configuration

### config.yaml Structure

```yaml
source:
  ref: upstream/main  # what to merge from

target:
  workdir: /path/to/repository
  branch: stable

build_test:
  command: make test  # can be any command
  output_dir: {workdir}/.splintercat/build-logs
  timeout: 14400  # 4 hours in seconds

llm:
  api_key: ${OPENROUTER_API_KEY}  # environment variable
  base_url: https://openrouter.ai/api/v1

  resolver_model: openai/gpt-4o-mini
  summarizer_model: openai/gpt-4o-mini
  planner_model: anthropic/claude-sonnet-4

imerge:
  name: upstream-merge  # name for this merge operation
  goal: merge  # produces single merge commit

merge:
  max_retries: 5  # maximum recovery attempts
  strategies_available: [optimistic, batch, per_conflict]
  default_batch_size: 10
```

### Environment Variables

- **OPENROUTER_API_KEY**: Required for LLM access via OpenRouter
- Other environment variables can override config values via pydantic-settings

### Command-Line Options

Via pydantic-settings CLI integration:
- `--verbose`: Enable debug logging to console
- `--interactive`: Prompt before executing commands (using existing CommandRunner feature)
- Configuration fields can be overridden: `--llm.planner_model=...`

## State Management

### Pydantic AI Graph State Schema

Pydantic models (to be defined during implementation):

```python
class MergeWorkflowState(BaseModel):
    # git-imerge tracking
    imerge_name: str
    workdir: Path
    source_ref: str
    target_branch: str

    # Current work
    current_strategy: str  # optimistic | batch | per_conflict
    conflicts_in_batch: list[ConflictInfo]

    # History
    attempts: list[MergeAttempt]
    resolutions: list[ConflictResolution]

    # Status
    status: str  # in_progress | complete | failed

class ConflictInfo(BaseModel):
    i1: int  # commit index from branch 1
    i2: int  # commit index from branch 2
    files: list[str]

class MergeAttempt(BaseModel):
    attempt_number: int
    strategy: str
    conflicts_resolved: list[ConflictResolution]
    build_result: BuildResult | None
    failure_summary: str | None
    planner_decision: str | None

class ConflictResolution(BaseModel):
    conflict_pair: tuple[int, int]
    files: list[str]
    resolution: str  # resolved content
    attempt_number: int
    timestamp: datetime

class BuildResult(BaseModel):
    success: bool
    log_file: Path
    returncode: int
    timestamp: datetime
```

### Build Logs

- **Location**: `{workdir}/.splintercat/build-logs/`
- **Naming**: `build-{timestamp}.log`
- **Retention**: Never auto-deleted (kept for debugging and analysis)
- **Format**: Complete stdout and stderr from build/test command

### Logging

**Console output**:
- INFO level by default
- User-facing progress messages
- Key decisions and actions
- `--verbose` flag enables DEBUG level

**File output** (`splintercat.log`):
- DEBUG level always
- All details including:
  - Full LLM prompts and responses
  - git-imerge state transitions
  - Build command execution
  - Decision reasoning
- Rotation: 10MB per file
- Retention: 7 days

## Merge Strategies

### optimistic

**Approach**: Resolve all conflicts first, then build/test once at the end

**Advantages**:
- Fastest if successful
- Minimum number of builds (1)

**Disadvantages**:
- Hard to isolate which resolution caused failure
- Requires sophisticated recovery strategies

**Best for**: Small merges or when conflicts are likely unrelated

### batch

**Approach**: Resolve N conflicts (configurable), build/test, repeat

**Advantages**:
- Balanced between speed and isolation
- Reasonable blast radius for failures
- Fewer builds than per-conflict

**Disadvantages**:
- Still need to isolate within batch on failure
- May waste time if early conflicts break build

**Best for**: Medium to large merges (default strategy)

**Default batch_size**: 10 conflicts

### per_conflict

**Approach**: Resolve one conflict, build/test immediately, repeat

**Advantages**:
- Best isolation of failures
- Know exactly which resolution caused problem
- Safest approach

**Disadvantages**:
- Slowest (most builds)
- Build overhead for each conflict

**Best for**: Fallback when other strategies fail repeatedly, or critical merges

## Recovery Strategies

Planner chooses from these options when build/test fails:

### retry-all

**Approach**: Re-resolve all conflicts with failure context added

**When used**: Failure suggests systemic misunderstanding of codebase or merge intent

**Process**:
1. Keep original resolutions for comparison
2. Re-resolve all conflicts with prompt context: "Previous attempt failed with: {summary}"
3. Build/test again

### retry-specific

**Approach**: Planner identifies which resolution(s) likely caused failure, re-resolve only those

**When used**: Build failure clearly relates to specific files/subsystems

**Process**:
1. Planner analyzes failure summary + conflict resolutions
2. Planner specifies which conflict pairs to retry
3. Re-resolve only those conflicts
4. Build/test again

**Fastest recovery** if Planner's analysis is correct

### bisect

**Approach**: Binary search through resolutions to find problematic one(s)

**When used**: Planner cannot identify culprit from failure summary

**Process**:
1. Apply first half of resolutions, build/test
2. Apply second half of resolutions, build/test
3. Narrow down to problematic resolution(s)
4. Re-resolve identified conflicts

**Build cost**: O(log N) where N = number of resolutions

### switch-strategy

**Approach**: Change to more conservative strategy

**When used**: Current strategy keeps failing, need better isolation

**Typical progression**: optimistic → batch → per-conflict

**Process**:
1. Revert to clean state
2. Restart with new strategy
3. Continue from beginning with better isolation

### abort

**Approach**: Report to human for manual intervention

**When used**:
- max_retries exceeded
- Planner determines problem is beyond automated recovery
- Repeated failures with no clear pattern

**Process**:
1. Save all state and logs
2. Generate summary report for human
3. Exit cleanly

## LLM Responsibilities

### Conflict Resolver

**Task**: Mechanical conflict resolution

**Prompt template** (to be refined):
```
Resolve the merge conflict in {filepath}.

Conflict content:
{conflict_markers_and_code}

Context:
- Commit A ({sha1_a}): {message_a}
- Commit B ({sha2_b}): {message_b}

[If retry:]
Previous resolution failed with: {failure_summary}

Instructions:
- Output ONLY the resolved file content
- Remove all conflict markers (<<<<<<< ======= >>>>>>>)
- No explanations, no markdown code blocks
- Preserve correct syntax and semantics
```

**Output validation**:
- Check for remaining conflict markers (error if present)
- Basic syntax validation if possible

### Build Summarizer

**Task**: Extract actionable information from build/test logs

**Prompt template** (to be refined):
```
Analyze this build/test log and extract the root cause of failure.

Log file: {log_path}

Instructions:
- Focus on the FIRST error (not cascading errors)
- Identify specific file and line numbers
- Distinguish root cause from symptoms
- Include relevant error message excerpt

Output format (structured):
- error_type: [compile_error | link_error | test_failure | timeout]
- location: [file:line or test name]
- root_cause: [one-sentence description]
- excerpt: [relevant error message]
```

**Output parsing**: Structured format for Planner consumption

### Strategic Planner

**Task**: Make all strategic and tactical decisions

#### Decision Point 1: Initial Strategy Selection

**Prompt template** (to be refined):
```
You are planning a git merge strategy.

Merge details:
- Source: {source_ref} ({num_source_commits} commits)
- Target: {target_branch} ({num_target_commits} commits)
- Estimated conflicts: {estimate if available}

Available strategies:
- optimistic: Resolve all conflicts, then test once (fast, risky)
- batch: Resolve {default_batch_size} conflicts, test, repeat (balanced)
- per_conflict: Resolve one, test, repeat (slow, safe)

Choose a strategy and explain your reasoning.

Output format:
- strategy: [optimistic | batch | per_conflict]
- batch_size: [number, if batch strategy]
- reasoning: [explanation]
```

#### Decision Point 2: Failure Recovery

**Prompt template** (to be refined):
```
Merge attempt failed. Analyze and choose recovery approach.

Current attempt:
- Strategy: {strategy}
- Conflicts resolved: {count}
- Build result: FAILED

Build failure summary:
{summarizer_output}

Conflicts resolved in this attempt:
{list of (i1,i2): files affected}

Previous attempts:
{attempt_history if any}

Available recovery options:
1. retry-all: Re-resolve all conflicts with failure context
2. retry-specific: Identify and re-resolve specific conflicts (specify which)
3. bisect: Binary search to find problematic resolution
4. switch-strategy: Change to {more_conservative_option}
5. abort: Report to human (use if problem seems beyond automated recovery)

Choose an option and explain your reasoning.
If retry-specific, list which conflict pairs (i1,i2) to retry.

Output format:
- decision: [retry-all | retry-specific | bisect | switch-strategy | abort]
- conflicts_to_retry: [(i1,i2), ...] (if retry-specific)
- new_strategy: [strategy name] (if switch-strategy)
- reasoning: [explanation]
```

#### Decision Point 3: Repeated Failures

**Prompt template** (to be refined):
```
Multiple recovery attempts have failed. Analyze pattern and decide.

Attempt history:
{for each attempt:}
  Attempt {n}:
  - Strategy: {strategy}
  - Recovery: {recovery_approach}
  - Result: FAILED
  - Error: {summary}

Pattern analysis questions:
- Same files failing repeatedly?
- Same error types?
- Getting closer to success or not?

Decision:
- Continue with different approach?
- Abort and report to human?

Output format:
- decision: [continue | abort]
- approach: [strategy/recovery if continue]
- pattern_analysis: [what pattern you observed]
- reasoning: [explanation]
```

## Failure Handling

### Build/Test Failures

**Process**:
1. Capture complete stdout and stderr to timestamped log file
2. Invoke Summarizer LLM with log path
3. Invoke Planner LLM with summary and context
4. Execute Planner's decision
5. Repeat until success or max_retries or abort

**Retry limit**: Configurable `max_retries` (default: 5)

### LLM Failures

**API errors** (network, rate limit, etc.):
- Retry with exponential backoff
- Log error details
- If repeated failures: abort merge with error report

**Invalid output** (unparseable, incomplete):
- Log the invalid output
- Retry once
- If still invalid: abort merge with error report

**Timeout**:
- Log timeout details
- Consider increasing timeout in config
- Abort merge with recommendation to adjust timeout

**Context too large** (exceeds model's context window):
- Attempt intelligent truncation
- If truncation not viable: abort with error report
- Document context size in logs for debugging

### git-imerge Failures

**Unclean working tree**:
- Abort immediately with clear error message
- Instruct user to clean working tree or stash changes

**Invalid state** (corrupted refs):
- Cannot resume merge
- Report error with details
- Suggest removing `refs/imerge/{name}` to start fresh

**Other git-imerge exceptions**:
- Log full exception details
- Abort merge
- Report error to user

## MVP Scope

### Included in MVP

- ✓ Automatic conflict resolution with LLM
- ✓ Three merge strategies (optimistic, batch, per-conflict)
- ✓ Build/test validation at strategic points
- ✓ LLM-driven strategic planning and recovery
- ✓ Multiple recovery strategies (retry-all, retry-specific, bisect, switch-strategy, abort)
- ✓ Complete merge to single commit preserving original hashes
- ✓ Resume capability (interrupt and continue)
- ✓ Full logging of all decisions and actions
- ✓ Configuration-driven (YAML + env vars + CLI)

### Not Included (Future Enhancements)

- ✗ Human-in-loop approval gates (runs fully automated in MVP)
- ✗ Cost tracking and optimization
- ✗ Learning from historical merge patterns
- ✗ Resolution validation LLM (check before building)
- ✗ Interactive mode for conflict review
- ✗ Sub-commit subdivision (commits are atomic in git-imerge)
- ✗ Custom conflict prioritization (MVP follows git-imerge's order)
- ✗ Parallel conflict resolution for independent files
- ✗ Web UI for monitoring merge progress
- ✗ CI/CD integration hooks

## Success Criteria

### Per-Merge Success

A merge is successful when:
- Merge completes without human intervention
- Build passes after final merge
- Tests pass after final merge
- Final result is single two-parent merge commit
- Original commit hashes from both branches preserved
- All decisions and resolutions logged for review

### MVP Validation Success

MVP is validated when:
- Successfully merges a real large upstream branch (1000+ commits)
- Demonstrates recovery from build failures
- Shows Planner making intelligent strategic decisions
- Logs are sufficient for understanding what happened and why
- Recovery strategies successfully isolate and fix problematic resolutions
- Can resume an interrupted merge

## Future Enhancements

Post-MVP features, priority to be determined:

### Human-in-Loop Mode
- Configurable approval gates (before merge, before recovery, etc.)
- Interactive conflict review before resolution
- Approval required for strategy changes

### Cost Tracking
- Track API costs per merge operation
- Report costs by LLM role (resolver vs. summarizer vs. planner)
- Budget limits and warnings
- Cost optimization recommendations

### Learning System
- Store merge history in database
- Analyze patterns in successful/failed resolutions
- Improve prompts based on outcomes
- Suggest preemptive strategy based on merge characteristics

### Resolution Validation
- Additional LLM pass to validate resolution before building
- Sanity checks: syntax, semantic consistency, obvious errors
- Catch problems before expensive build

### Custom Conflict Ordering
- Planner chooses which conflicts to tackle first from frontier
- Strategic ordering based on:
  - File complexity
  - Subsystem criticality
  - Likelihood of success
  - Dependencies between conflicts

### Parallel Processing
- Resolve independent conflicts in parallel
- Multiple LLM requests concurrently
- Requires dependency analysis between conflicts

### CI/CD Integration
- Webhooks for merge progress/completion
- Integration with GitHub/GitLab PR systems
- Automated merge of approved upstream branches

### Web UI
- Real-time merge progress visualization
- Interactive log viewing
- Manual intervention when needed
- Historical merge review

## References

- [git-imerge](https://github.com/mhagger/git-imerge) - Incremental merge tool
- [Pydantic AI](https://ai.pydantic.dev/) - LLM orchestration and graph workflows
- [OpenRouter](https://openrouter.ai/) - Unified LLM API access
