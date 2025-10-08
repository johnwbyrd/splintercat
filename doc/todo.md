# Splintercat Implementation TODO

Implementation order for MVP, organized by phases. This guide assumes the tool-based conflict resolution architecture from merge-resolver.md.

## Phase 1: Core Infrastructure

Goal: Get basic plumbing working independently with git-imerge

### 1. Update config.py - DONE

Configuration classes are implemented:
- ModelConfig (api_key, base_url, resolver_model, summarizer_model, planner_model)
- BuildConfig (command, output_dir, timeout) - for fast incremental builds to detect compile errors
- TestConfig (command, output_dir, timeout) - for complete test runs to validate correctness
- IMergeConfig (name, goal)
- Settings with template substitution for {target.workdir}

### 2. Implement git-imerge wrapper (src/git/imerge.py)

Full implementation, not a stub. This is foundational for the entire system.

**Core Methods:**

start_merge(source_ref: str, target_branch: str)
- Execute: git imerge start --name={name} --goal={goal} --branch={target_branch} {source_ref}
- Verify imerge state is created in refs/imerge/{name}/
- Check out the scratch branch (refs/heads/imerge/{name})
- Return success/failure

get_current_conflict() -> tuple[int, int] | None
- Check if git-imerge is waiting for manual merge
- Parse git status to detect conflict state
- Return (i1, i2) pair for current conflict, or None if no conflict waiting
- This is what drives the resolution loop

get_conflict_files(i1: int, i2: int) -> list[str]
- Execute: git diff --name-only --diff-filter=U
- Return list of files with conflict markers for current merge

continue_after_resolution()
- Execute: git imerge continue
- This incorporates the staged resolution and advances to next conflict
- May complete merge if this was the last conflict
- Return whether more conflicts remain

is_complete() -> bool
- Check if git-imerge has finished all pairwise merges
- Look for completion indicators in git-imerge state
- Return True if ready for finalization

finalize() -> str
- Execute: git imerge finish
- This simplifies to single two-parent merge commit
- Return the final merge commit SHA

**Error Handling:**
- Detect unclean working tree (common error)
- Handle case where imerge name already exists
- Detect and report git-imerge internal errors
- Provide actionable error messages

**Testing Strategy:**
- Test with llvm-mos repository (use reset-branches.bash first)
- Start merge, verify scratch branch created
- Manually create conflict, verify get_current_conflict() detects it
- Manually resolve and stage, verify continue_after_resolution() works
- Complete full merge cycle, verify finalize() produces correct commit

**Key Insight:**
git-imerge maintains state in refs/imerge/{name}/ and uses a scratch branch at refs/heads/imerge/{name}. We must respect this workflow: start → [conflict → resolve → stage → continue] → finish.

### 3. Implement BuildRunner (src/runner/build.py)

Execute build commands with proper logging and timeout handling for fast incremental builds.

**Core Method:**

run_build(command: str) -> BuildResult
- Create output_dir if it doesn't exist
- Generate timestamped log filename: build-{YYYYMMDD-HHMMSS}.log
- Execute command in workdir with timeout
- Stream output to both console (INFO level) and log file
- Handle timeout gracefully (kill process, mark as timeout failure)
- Return BuildResult(success, log_file, returncode, timestamp)

**BuildResult Model (src/state/build.py):**
- success: bool
- log_file: Path
- returncode: int
- timestamp: datetime

**Implementation Details:**
- Use CommandRunner for execution with real-time output
- Write all stdout/stderr to log file as execution happens
- On timeout: log "Build timed out after {timeout} seconds" and kill process
- Ensure log file is flushed and closed even on errors
- Log file naming must be consistent for Summarizer to find them

**Error Handling:**
- Timeout: SIGTERM then SIGKILL if needed
- Command not found: clear error message
- Working directory doesn't exist: check before running
- Disk full: catch and report

**Testing Strategy:**
- Test with fast command (echo "hello") - should succeed immediately
- Test with slow command and short timeout - should timeout properly
- Test with failing command (false) - should capture failure
- Test with command that writes to stderr - should capture both streams
- Verify log files are written to correct location with correct naming

### 4. Implement TestRunner (src/runner/test.py)

Execute test commands with proper logging and timeout handling for complete test validation.

**Core Method:**

run_test(command: str) -> TestResult
- Create output_dir if it doesn't exist
- Generate timestamped log filename: test-{YYYYMMDD-HHMMSS}.log
- Execute command in workdir with timeout
- Stream output to both console (INFO level) and log file
- Handle timeout gracefully (kill process, mark as timeout failure)
- Return TestResult(success, log_file, returncode, timestamp)

**TestResult Model (src/state/test.py):**
- success: bool
- log_file: Path
- returncode: int
- timestamp: datetime

**Implementation Details:**
- Use CommandRunner for execution with real-time output
- Write all stdout/stderr to log file as execution happens
- On timeout: log "Test timed out after {timeout} seconds" and kill process
- Ensure log file is flushed and closed even on errors
- Log file naming must be consistent for Summarizer to find them

**Error Handling:**
- Timeout: SIGTERM then SIGKILL if needed
- Command not found: clear error message
- Working directory doesn't exist: check before running
- Disk full: catch and report

**Testing Strategy:**
- Test with ninja check-llvm (or subset) and verify log captured
- Test timeout with sleep command
- Test failure capture with command that exits non-zero
- Verify log file permissions and location

### 5. Test infrastructure independently

Before combining components, verify each works in isolation.

**git-imerge wrapper tests:**
- Start a merge between heaven/main and stable-test
- Verify conflict detection works
- Manually resolve a conflict and verify continue works
- Complete a full merge cycle
- Verify final merge commit has two parents and correct tree

**BuildRunner tests:**
- Run fast incremental build (single file) and verify log captured
- Test timeout with sleep command
- Test failure capture with command that exits non-zero
- Verify log file permissions and location

**TestRunner tests:**
- Run ninja check-llvm (or subset) and verify log captured
- Test timeout with long-running test
- Test failure capture with failing test
- Verify log file permissions and location

**Config tests:**
- Load config.yaml and verify all fields parse correctly
- Test template substitution: {target.workdir} replaced properly
- Test .env file loading for MODEL__API_KEY
- Test CLI arg override: --verbose=true

**Success Criteria:**
- git-imerge can start, detect conflicts, continue, and finalize
- BuildRunner captures output and handles timeouts for fast builds
- TestRunner captures output and handles timeouts for full test runs
- Config loads from all sources (YAML, .env, CLI)

## Phase 2: Tool-Based Resolver

Goal: Get conflict resolution working with tool-based architecture

### 6. Implement tool system (src/tools/)

Create infrastructure for LLM to use tools via function calling.

**Base Tool Class (src/tools/base.py):**

Tool protocol with:
- name: str - tool identifier for LLM
- description: str - what the tool does (for function schema)
- parameters: dict - JSON schema of parameters
- execute(**kwargs) -> str - runs tool, returns human-readable result

**Tool Registry (src/tools/registry.py):**

ToolRegistry class:
- register(tool: Tool) - add tool to registry
- get_tool(name: str) -> Tool - retrieve tool by name
- get_schemas() -> list[dict] - return LangChain function schemas for all tools
- execute_tool(name: str, **kwargs) -> str - execute tool by name

**Layer 1 Tools (src/tools/conflict.py):**

ViewConflictTool:
- Parameters: file (str), conflict_num (int), context_lines (int, default=10)
- Execution:
  - Read file from workdir
  - Parse conflict markers (<<<<<<< ======= >>>>>>>)
  - Find Nth conflict (1-indexed)
  - Extract context_lines before and after conflict block
  - Format output with line numbers
  - Return human-readable text showing conflict with context
- Error handling:
  - File not found: clear error
  - Conflict number out of range: report how many conflicts exist
  - No conflict markers: report file has no conflicts

ViewMoreContextTool:
- Parameters: file (str), conflict_num (int), before (int), after (int)
- Same as ViewConflictTool but with explicit before/after line counts
- Useful when LLM needs more context than default

ResolveConflictTool:
- Parameters: file (str), conflict_num (int), choice (str), custom_text (str | None)
- choice: "ours" | "theirs" | "both" | "custom"
- Execution:
  - Read file from workdir
  - Find Nth conflict
  - Apply resolution:
    - "ours": keep HEAD section, remove conflict markers
    - "theirs": keep incoming section, remove conflict markers
    - "both": keep both sections (ours then theirs), remove markers
    - "custom": replace entire conflict block with custom_text
  - Write resolved file back to workdir
  - Stage file with git add
  - Return confirmation message
- Error handling:
  - Invalid choice: report valid options
  - custom_text required but missing: clear error
  - Git add fails: report staging error

**Output Format Example:**

ViewConflictTool output format:
  File: llvm/include/llvm/CodeGen/LiveRangeEdit.h
  Conflict 1 of 2

  Lines 70-85 showing:
    70:   MachineRegisterInfo &MRI;
    71:   LiveIntervals &LIS;
    72:   VirtRegMap *VRM;
    73:   const TargetInstrInfo &TII;
    74:   Delegate *const TheDelegate;
    75:
    76:   const unsigned FirstNew;
    77:
    78: <<<<<<< HEAD
    79:   bool EnableRemat = true;
    80:   bool ScannedRemattable = false;
    81:
    82: =======
    83: >>>>>>> heaven/main
    84:   /// DeadRemats - The saved instructions which have already been dead
    85:   SmallVector<MachineInstr *, 32> DeadRemats;

ResolveConflictTool output format:
  Resolved conflict 1 in llvm/include/llvm/CodeGen/LiveRangeEdit.h
  Choice: theirs (accepted deletion of EnableRemat and ScannedRemattable)
  File staged with git add

**Testing Strategy:**
- Create test files with known conflict markers
- Test ViewConflictTool with various context_lines values
- Test ResolveConflictTool with all choice types
- Verify files are modified correctly
- Verify git staging works
- Test error cases (missing file, invalid conflict_num, etc.)

### 7. Implement Resolver with function calling (src/model/resolver.py)

LLM-based resolver that uses tools to investigate and resolve conflicts.

**Resolver Class:**

__init__(model_config: ModelConfig, tool_registry: ToolRegistry)
- Initialize LangChain ChatOpenAI with model config
- Bind tools from registry using .bind_tools(tool_schemas)
- Enable function calling mode
- Store config for logging

resolve_conflict_interactive(file: str, conflict_num: int, context: dict) -> ResolutionResult
- context contains: commit messages, previous failure info (if retry)
- Start conversation with initial prompt
- Loop until resolution complete:
  - Call LLM with conversation history
  - If LLM returns tool call: execute tool, add result to conversation
  - If LLM returns text: check if it's explanation/reasoning
  - Continue until LLM calls ResolveConflictTool
- Extract reasoning from conversation
- Return ResolutionResult with decision and reasoning

**Initial Prompt Template:**

You are resolving merge conflict {conflict_num} in file {file}.

Context:
- Merging {source_ref} into {target_branch}
- Commit A (HEAD): {commit_a_message}
- Commit B (incoming): {commit_b_message}

If retry: Previous resolution attempt failed with this summary:
  {failure_summary}

You have these tools available:
- view_conflict: See the conflict with surrounding context
- view_more_context: Expand context if you need more information
- resolve_conflict: Apply your resolution decision

Process:
1. Use view_conflict to see the conflict
2. Investigate if needed (you'll get more tools in later phases)
3. Decide on resolution: keep ours, keep theirs, keep both, or write custom
4. Use resolve_conflict to apply your decision
5. Explain your reasoning

Start by viewing the conflict.

**ResolutionResult Model (src/state/conflict.py):**

ResolutionResult:
- file: str
- conflict_num: int
- choice: str (ours/theirs/both/custom)
- custom_text: str | None
- reasoning: str - LLM's explanation
- tool_calls: list[dict] - log of all tool invocations
- timestamp: datetime

**Multi-Turn Conversation Handling:**

The resolver must handle a conversation loop:
1. Send prompt
2. LLM responds with tool call (e.g., view_conflict)
3. Execute tool, get result
4. Add tool result to conversation
5. Send conversation back to LLM
6. LLM analyzes, may call more tools or resolve
7. Repeat until ResolveConflictTool is called

Use LangChain's standard tool calling pattern:
- Create messages list starting with SystemMessage containing the prompt
- Loop: invoke LLM, check for tool_calls in response
- For each tool_call: execute tool, append ToolMessage with result
- Check if resolve_conflict was called, if so break
- Otherwise append response to messages and continue loop

**Logging:**
- Log initial prompt at DEBUG level
- Log every tool call and result at DEBUG level
- Log LLM reasoning at INFO level
- Log final resolution decision at INFO level

**Error Handling:**
- LLM doesn't call any tools: prompt again, request tool usage
- LLM calls invalid tool: error message, list valid tools
- Tool execution fails: report error to LLM, let it adjust
- LLM loops without resolving: timeout after 10 turns, report failure
- API errors: retry with exponential backoff (3 attempts)

**Testing Strategy:**
- Test with simple conflict (delete vs. keep code)
- Verify LLM calls view_conflict first
- Verify tool results appear in conversation
- Verify LLM eventually calls resolve_conflict
- Test with conflict requiring more context
- Verify reasoning is captured
- Test retry scenario (pass failure_context)
- Test error cases (API failure, timeout)

**Success Criteria:**
- LLM reliably uses view_conflict before resolving
- LLM provides reasoning for decisions
- All tool calls and results are logged
- Resolution is staged with git add
- Conversation completes within reasonable turns (typically 2-4)

## Phase 3: Simple Linear Flow

Goal: End-to-end merge with per-conflict strategy using git-imerge

### 8. Implement workflow nodes (simple versions)

These are standalone functions, not yet connected via LangGraph. Each takes state dict and returns updated state dict.

**Initialize Node (src/workflow/nodes/initialize.py):**

initialize(state: dict) -> dict
- Get source_ref, target_branch from state
- Create IMergeWrapper instance
- Call start_merge(source_ref, target_branch)
- Verify merge started successfully
- Update state with:
  - imerge_name: str
  - status: "initialized"
  - conflicts_remaining: True
- Log: "Initialized git-imerge merge of {source_ref} into {target_branch}"
- Return updated state

**Resolve Conflicts Node (src/workflow/nodes/resolve_conflicts.py):**

resolve_conflicts(state: dict) -> dict
- Get IMergeWrapper instance from state
- Loop:
  - conflict = imerge.get_current_conflict()
  - If conflict is None: break (no more conflicts)
  - files = imerge.get_conflict_files(*conflict)
  - For each file:
    - Parse conflicts in file (may be multiple per file)
    - For each conflict in file:
      - Call resolver.resolve_conflict_interactive(file, conflict_num, context)
      - Log resolution with reasoning
      - Store ResolutionResult in state.resolutions list
  - imerge.continue_after_resolution()
  - Test if this is per-conflict strategy: if so, break after one conflict
- Update state with:
  - resolutions: list[ResolutionResult]
  - conflicts_remaining: bool
- Return updated state

**Key Detail:**
A single merge commit pair (i1, i2) may have conflicts in multiple files. A single file may have multiple conflicts. The loop structure is:
- While conflict_pair exists from imerge.get_current_conflict():
  - Get files with conflicts for this pair
  - For each file:
    - Count conflicts in file
    - For each conflict_num from 1 to count:
      - Call resolve_conflict_interactive(file, conflict_num, context)
  - Call imerge.continue_after_resolution()
  - If strategy is per_conflict: break to test build after each conflict pair

**Build Node (src/workflow/nodes/build.py):**

build(state: dict) -> dict
- Get BuildRunner instance from state
- Get build command from config
- Call build_runner.run_build(command)
- Update state with:
  - build_result: BuildResult
  - build_success: bool
- Log result (success or failure with returncode)
- Return updated state

**Test Node (src/workflow/nodes/test.py):**

test(state: dict) -> dict
- Get TestRunner instance from state
- Get test command from config
- Call test_runner.run_test(command)
- Update state with:
  - test_result: TestResult
  - test_success: bool
- Log result (success or failure with returncode)
- Return updated state

**Finalize Node (src/workflow/nodes/finalize.py):**

finalize(state: dict) -> dict
- Get IMergeWrapper instance from state
- Call imerge.finalize()
- Get final merge commit SHA
- Update state with:
  - final_commit: str
  - status: "complete"
- Log: "Merge finalized to commit {sha}"
- Return updated state

### 9. Write simple main.py

Linear workflow without LangGraph, hardcoded per-conflict strategy.

**Structure:**

Main function:
- Load settings from config
- Setup logging based on verbosity
- Initialize components:
  - CommandRunner with interactive flag
  - IMergeWrapper with workdir and imerge name
  - ToolRegistry with Layer 1 tools (ViewConflict, ViewMoreContext, ResolveConflict)
  - Resolver with model config and tool registry
  - BuildRunner with workdir, build output_dir, and build timeout
  - TestRunner with workdir, test output_dir, and test timeout
- Create initial state dict with:
  - source_ref and target_branch from settings
  - empty resolutions list
  - component instances (imerge, resolver, build_runner, test_runner)
- Execute linear workflow:
  - Phase 1: Call initialize(state)
  - While conflicts_remaining:
    - Phase 2: Call resolve_conflicts(state) which resolves ONE conflict pair
    - Phase 3: Call build(state)
    - If build failed: log error with log file path and exit with error code
    - Phase 4: Call test(state)
    - If test failed: log error with log file path and exit with error code
  - Phase 5: Call finalize(state)
- Log success with final commit SHA

**Key Points:**
- Hardcoded per-conflict strategy (resolve one pair, build, test, repeat)
- No recovery - exits on first build or test failure
- No intelligence - just execute steps in order
- All components initialized upfront
- State passed between nodes as dict

**Why per-conflict?**
It's the simplest to implement and debug. Each conflict resolution is immediately validated with a build and test. If something breaks, we know exactly which resolution caused it. We add batch and optimistic strategies later when we add the Planner.

### 10. Test end-to-end

Use llvm-mos repository with heaven/main merge.

**Test Setup:**
- Run reset-branches.bash to prepare clean stable-test branch
- Configure config.yaml:
  - source.ref: heaven/main
  - target.branch: stable-test
  - target.workdir: /home/jbyrd/git/llvm-mos
  - build.command: cd {target.workdir}/build && ninja (fast incremental)
  - test.command: cd {target.workdir}/build && ninja check-llvm (or subset)
  - model.resolver_model: cheap model for testing

**Test Execution:**
- Run: python main.py
- Observe:
  - git-imerge starts merge
  - First conflict detected
  - LLM uses view_conflict tool
  - LLM resolves conflict with reasoning
  - Build runs (should be fast with incremental)
  - Tests run (may take time)
  - Process repeats for next conflict
  - Eventually finalizes to single merge commit

**Expected Duration:**
With approximately 10-20 conflicts and 30-60 min test runs per conflict, this could take 5-20 hours. Consider:
- Use smaller test command for testing (single file or small subsystem)
- Use verbose logging to see progress
- Be patient - this proves the system works

**Success Criteria:**
- Merge completes without crashes
- All conflicts are resolved
- All builds and tests pass
- Final merge commit has two parents
- Final commit tree matches expected result
- All decisions are logged with reasoning

**Known Issues to Watch:**
- LLM may struggle with complex conflicts (expected in Phase 3)
- Build or test may timeout (adjust config if needed)
- git-imerge state may get confused (run reset-branches.bash to restart)

## Phase 4: Failure Handling

Goal: Detect and report failures intelligently

### 11. Implement Summarizer (src/model/summarizer.py)

LLM that extracts actionable information from build and test logs.

**Summarizer Class:**

__init__(model_config: ModelConfig)
- Initialize LangChain ChatOpenAI with summarizer_model
- Configure for structured output
- Use cheap/fast model (e.g., gpt-4o-mini)

summarize_failure(log_file: Path) -> BuildFailureSummary
- Read log file (may be large, 10MB+)
- If too large for context: implement intelligent truncation
  - Keep first 1000 lines (context)
  - Keep last 5000 lines (where errors usually are)
  - Keep any lines with "error" or "failed" keywords
- Send to LLM with prompt requesting structured extraction
- Parse response into BuildFailureSummary
- Return summary

**Prompt Template:**

Analyze this build/test log and extract the root cause of failure.

Focus on:
- The FIRST error (ignore cascading errors)
- Specific file and line number if available
- Root cause vs. symptom distinction
- Relevant error message excerpt

Build/test command: {command}
Log file: {log_file}

Log content:
{truncated_log}

Output structured JSON with these fields:
- error_type: one of "compile_error", "link_error", "test_failure", or "timeout"
- location: file:line or test name or null if not available
- root_cause: one-sentence description of the problem
- excerpt: relevant error message excerpt (10-20 lines max)

Be concise. Focus on actionable information.

**BuildFailureSummary Model (src/state/build.py):**

BuildFailureSummary:
- error_type: str (compile_error, link_error, test_failure, timeout)
- location: str | None (file:line or test name)
- root_cause: str (one-sentence description)
- excerpt: str (relevant error message excerpt)
- timestamp: datetime

**Log Truncation Strategy:**

For large logs:
1. Calculate size and line count
2. If over 100k lines or 5MB: truncate intelligently
3. Keep structure: [header] ... [middle excerpt] ... [tail with errors]
4. Preserve enough context for LLM to understand what was being built

**Error Handling:**
- Log file not found: clear error
- Log file empty: report, return empty summary
- LLM response not valid JSON: retry once, then fail gracefully
- LLM doesn't provide all fields: fill in defaults

**Testing Strategy:**
- Create mock log with compile error (missing header)
- Create mock log with link error (undefined reference)
- Create mock log with test failure (assertion failed)
- Create mock log with timeout message
- Test with real LLVM build or test failure log
- Verify summarizer extracts correct error type and location

### 12. Implement SummarizeFailure node (src/workflow/nodes/summarize_failure.py)

summarize_failure(state: dict) -> dict
- Get Summarizer instance from state (or create)
- Get BuildResult or TestResult from state (has log_file path)
- Call summarizer.summarize_failure(log_file)
- Update state with:
  - failure_summary: BuildFailureSummary
- Log summary at INFO level for user visibility
- Return updated state

**Logging Output Example:**

Build/test failed: compile_error
Location: llvm/lib/Target/MOS/MOSInstrInfo.cpp:145
Root cause: Undefined method 'getRegisterInfo()' called on MOSSubtarget
Excerpt:
  MOSInstrInfo.cpp:145:23: error: no member named 'getRegisterInfo' in 'MOSSubtarget'
    return Subtarget->getRegisterInfo()->getFrameRegister(*MF);
           ~~~~~~~~~~  ^
  1 error generated.

### 13. Update main.py

Add conditional handling for build and test failures.

**Changes to main.py:**

After build node:
- If build failed:
  - Log warning about build failure
  - Create Summarizer instance if needed
  - Add to state
  - Call summarize_failure(state)
  - Extract summary from state
  - Log detailed failure summary:
    - Type, location, root cause
    - Log file path for deep inspection
  - Log "No automatic recovery yet. Exiting."
  - Exit with error code

After test node:
- If test failed:
  - Log warning about test failure
  - Create Summarizer instance if needed
  - Add to state
  - Call summarize_failure(state)
  - Extract summary from state
  - Log detailed failure summary:
    - Type, location, root cause
    - Log file path for deep inspection
  - Log "No automatic recovery yet. Exiting."
  - Exit with error code

**Still no automatic recovery** - we just report the failure intelligently and exit.

### 14. Test with intentional failures

Create scenarios that will fail builds or tests to verify summarizer works.

**Test Scenario 1: Compile Error**

Modify a resolution to introduce a syntax error:
- Manually edit resolved file to add typo or remove semicolon
- Let build run and fail
- Verify summarizer identifies compile error and location

**Test Scenario 2: Test Failure**

Resolve a conflict incorrectly (e.g., keep wrong version):
- Force a "wrong" resolution by editing after LLM resolves
- Let tests run and fail
- Verify summarizer identifies test failure and test name

**Test Scenario 3: Link Error**

Delete a function definition that's needed:
- Resolve conflict by choosing deletion when should keep
- Let build get to link stage and fail
- Verify summarizer identifies link error and symbol

**Success Criteria:**
- Summarizer correctly identifies error type in all scenarios
- Location information is accurate and useful
- Root cause description is actionable
- User can understand what went wrong from the summary
- Log file path is provided for deep debugging

## Phase 5: Strategic Planning

Goal: Model makes strategic decisions about merge approach and recovery

### 15. Implement Planner (src/model/planner.py)

LLM that makes high-level strategic decisions.

**Planner Class:**

__init__(model_config: ModelConfig)
- Initialize LangChain ChatOpenAI with planner_model
- Use smart/expensive model (e.g., claude-sonnet-4, gpt-4)
- Configure for structured output with reasoning

choose_initial_strategy(merge_context: MergeContext) -> StrategyDecision
- Analyze merge scope (commit counts, affected subsystems)
- Choose strategy: optimistic | batch | per_conflict
- Set parameters (batch_size if batch strategy)
- Provide reasoning for decision
- Return StrategyDecision

plan_recovery(failure_context: FailureContext) -> RecoveryDecision
- Analyze what failed and why
- Review previous attempts and patterns
- Choose recovery approach:
  - retry-all: Re-resolve all conflicts with failure context
  - retry-specific: Identify and re-resolve specific conflicts
  - bisect: Binary search for problematic resolution
  - switch-strategy: Change to more conservative approach
  - abort: Report to human
- If retry-specific: specify which conflict pairs to retry
- If switch-strategy: specify new strategy
- Provide reasoning for decision
- Return RecoveryDecision

**MergeContext Model (src/state/workflow.py):**

MergeContext:
- source_ref: str
- target_branch: str
- num_source_commits: int (from git log)
- num_target_commits: int (from git log)
- estimated_conflicts: int | None (from git merge --no-commit dry run)
- available_strategies: list[str]
- default_batch_size: int

**StrategyDecision Model (src/state/workflow.py):**

StrategyDecision:
- strategy: str (optimistic | batch | per_conflict)
- batch_size: int | None (required if batch strategy)
- reasoning: str
- timestamp: datetime

**FailureContext Model (src/state/workflow.py):**

FailureContext:
- current_strategy: str
- conflicts_resolved: int
- build_result: BuildResult (if build failed)
- test_result: TestResult (if test failed)
- failure_summary: BuildFailureSummary
- resolutions: list[ResolutionResult] (conflicts resolved in this attempt)
- previous_attempts: list[AttemptRecord] (history of failures)
- max_retries: int
- attempts_so_far: int

**RecoveryDecision Model (src/state/workflow.py):**

RecoveryDecision:
- decision: str (retry-all | retry-specific | bisect | switch-strategy | abort)
- conflicts_to_retry: list[tuple[int, int]] | None (if retry-specific)
- new_strategy: str | None (if switch-strategy)
- reasoning: str
- timestamp: datetime

**Prompt Templates:**

Initial Strategy Selection prompt:

You are planning a git merge strategy.

Merge details:
- Source: {source_ref} ({num_source_commits} commits)
- Target: {target_branch} ({num_target_commits} commits)
- Estimated conflicts: {estimated_conflicts or "unknown"}

Available strategies:
1. optimistic: Resolve all conflicts first, then build and test once
   - Fastest if successful (only 1 build and test)
   - Hard to isolate failures
2. batch: Resolve {default_batch_size} conflicts, build and test, repeat
   - Balanced approach
   - Reasonable isolation
   - Fewer builds and tests than per-conflict
3. per_conflict: Resolve one conflict, build and test, repeat
   - Slowest (most builds and tests)
   - Best isolation
   - Safest

Choose a strategy and set parameters. Explain your reasoning.

Output JSON with fields: strategy (one of the three options), batch_size (number, only if batch strategy), reasoning (explanation)

Recovery Planning prompt:

Merge attempt failed. Analyze and choose recovery approach.

Current attempt:
- Strategy: {strategy}
- Conflicts resolved: {count}
- Build or test result: FAILED

Failure summary:
{failure_summary}

Conflicts resolved in this attempt:
For each resolution: {i1}-{i2}: {files} - {choice} - {reasoning}

Previous attempts:
{attempt_history}

Available recovery options:
1. retry-all: Re-resolve all conflicts with failure context
2. retry-specific: Identify and re-resolve specific conflicts (list which)
3. bisect: Binary search to find problematic resolution
4. switch-strategy: Change to {more_conservative_option}
5. abort: Report to human (use if problem seems beyond automated recovery)

Attempt {attempts_so_far} of {max_retries}.

Choose an option and explain your reasoning.
If retry-specific, list which conflict pairs (i1,i2) to retry.

Output JSON with fields: decision (one of the five options), conflicts_to_retry (list of [i1, i2] pairs, only if retry-specific), new_strategy (strategy name, only if switch-strategy), reasoning (explanation)

**Error Handling:**
- LLM returns invalid strategy: default to per_conflict (safest)
- LLM returns invalid recovery decision: default to abort (safest)
- API errors: retry with backoff
- Response not valid JSON: parse reasoning from text, use conservative defaults

**Testing Strategy:**
- Test strategy selection with various commit counts:
  - 10 commits, few conflicts should choose optimistic
  - 100 commits, many conflicts should choose batch
  - Unknown conflict count should choose conservative
- Test recovery planning with various failure types:
  - Compile error in specific file should choose retry-specific
  - Link error affecting multiple files should choose retry-all
  - Repeated same error should choose switch-strategy
  - Multiple failures, no pattern should choose abort

### 16. Implement planning nodes

**PlanStrategy Node (src/workflow/nodes/plan_strategy.py):**

plan_strategy(state: dict) -> dict
- Create Planner instance
- Build MergeContext from state:
  - Get commit counts via git log
  - Estimate conflicts via git merge --no-commit (then abort)
  - Get available strategies from config
- Call planner.choose_initial_strategy(merge_context)
- Update state with:
  - strategy_decision: StrategyDecision
  - current_strategy: str
  - batch_size: int | None
- Log decision with reasoning at INFO level
- Return updated state

**PlanRecovery Node (src/workflow/nodes/plan_recovery.py):**

plan_recovery(state: dict) -> dict
- Get Planner instance (or create)
- Build FailureContext from state:
  - Get current strategy
  - Get conflicts resolved count
  - Get build or test result and failure summary
  - Get resolutions from current attempt
  - Get previous attempts from state history
  - Get max_retries and attempts_so_far from config/state
- Call planner.plan_recovery(failure_context)
- Update state with:
  - recovery_decision: RecoveryDecision
  - next_action: str (derived from decision)
- Log decision with reasoning at INFO level
- Return updated state

### 17. Update resolve_conflicts node for strategy support

**Changes to resolve_conflicts node:**

The node must now respect the strategy decision:

Define resolve_conflicts function:
- Get strategy from state current_strategy
- Get batch_size from state if applicable
- Initialize conflicts_resolved_this_batch to 0
- Get imerge and resolver from state
- Initialize empty resolutions list
- Loop:
  - Get conflict pair from imerge.get_current_conflict()
  - If None: set conflicts_remaining to False and break
  - Get files with conflicts for this pair
  - For each file:
    - Count conflicts in file
    - For each conflict_num from 1 to count:
      - Call resolver.resolve_conflict_interactive with context
      - Append result to resolutions
  - Call imerge.continue_after_resolution()
  - Increment conflicts_resolved_this_batch
  - Check strategy:
    - If per_conflict: break (build/test after each conflict pair)
    - If batch: break if conflicts_resolved_this_batch >= batch_size
    - If optimistic: continue (resolve all before building/testing)
- Update state with resolutions list
- Return updated state

### 18. Test planner in isolation

Test the Planner before integrating into workflow.

**Strategy Selection Tests:**

Create test cases with different MergeContext inputs:
- Small merge (10 commits, 5 conflicts) expect optimistic
- Medium merge (100 commits, 50 conflicts) expect batch
- Large merge (1000 commits, unknown conflicts) expect per_conflict or batch
- Verify reasoning makes sense in each case

**Recovery Planning Tests:**

Create test FailureContext inputs:
- Single failure, clear error in specific file expect retry-specific
- Single failure, unclear cause expect retry-all or bisect
- Multiple failures, same error expect switch-strategy
- Multiple failures, at max_retries expect abort
- Verify reasoning makes sense in each case

**Testing Script (tests/test_planner.py):**

Create unit tests that:
- Mock the LLM responses (use fixed JSON for predictable testing)
- Verify decision parsing works correctly
- Test with real LLM (mark as integration test, slower)
- Log all decisions and reasoning for manual review

**Success Criteria:**
- Planner makes reasonable decisions for various scenarios
- Reasoning is clear and actionable
- JSON parsing is robust
- Defaults are applied when LLM gives invalid response

## Phase 6: LangGraph Integration

Goal: Full MVP with state machine and recovery

### 19. Implement LangGraph workflow (src/workflow/graph.py)

Create state machine that orchestrates the entire merge process with recovery.

**State Schema (src/state/workflow.py):**

MergeWorkflowState (TypedDict):
- Core tracking:
  - imerge_name: str
  - source_ref: str
  - target_branch: str
  - workdir: Path
- Strategy:
  - current_strategy: str
  - batch_size: int | None
  - strategy_decision: StrategyDecision | None
- Current work:
  - conflicts_remaining: bool
  - resolutions: list[ResolutionResult]
  - current_attempt: int
- Build and test results:
  - build_result: BuildResult | None
  - test_result: TestResult | None
  - failure_summary: BuildFailureSummary | None
- Recovery:
  - recovery_decision: RecoveryDecision | None
  - attempt_history: list[AttemptRecord]
- Components (not serialized):
  - imerge: IMergeWrapper
  - resolver: Resolver
  - build_runner: BuildRunner
  - test_runner: TestRunner
  - summarizer: Summarizer
  - planner: Planner
- Final result:
  - final_commit: str | None
  - status: str (initialized | in_progress | complete | failed)

**Graph Structure:**

Nodes:
- initialize: Start git-imerge merge
- plan_strategy: Planner chooses initial strategy
- resolve_conflicts: Resolve according to strategy
- build: Run fast incremental build to detect compile errors
- test: Run complete test suite to validate correctness
- summarize_failure: Extract error information
- plan_recovery: Planner decides recovery approach
- execute_recovery: Apply recovery decision
- finalize: Simplify to single merge commit

Edges:
- START leads to initialize
- initialize leads to plan_strategy
- plan_strategy leads to resolve_conflicts
- resolve_conflicts leads to build
- build leads to conditional routing:
  - If success: go to test
  - If failure: go to summarize_failure
- test leads to conditional routing:
  - If success AND conflicts_remaining: go to resolve_conflicts (next batch)
  - If success AND NOT conflicts_remaining: go to finalize
  - If failure: go to summarize_failure
- summarize_failure leads to plan_recovery
- plan_recovery leads to conditional routing based on decision:
  - If retry-all: reset and go to resolve_conflicts
  - If retry-specific: go to resolve_conflicts with specific conflicts
  - If bisect: go to execute_bisect then resolve_conflicts
  - If switch-strategy: go to plan_strategy with new strategy
  - If abort: go to END with failure status
- execute_recovery leads to resolve_conflicts
- finalize leads to END

**Routing Functions:**

after_build(state: MergeWorkflowState) -> str:
- If build_result.success: return "test"
- Else: return "summarize_failure"

after_test(state: MergeWorkflowState) -> str:
- If test_result.success:
  - If conflicts_remaining: return "resolve_conflicts"
  - Else: return "finalize"
- Else: return "summarize_failure"

after_plan_recovery(state: MergeWorkflowState) -> str:
- Get decision from recovery_decision.decision
- If decision is "abort": return END
- If decision is "switch-strategy": return "plan_strategy"
- Else: return "execute_recovery"

**Retry Tracking:**

The graph must enforce max_retries:
- Increment current_attempt in execute_recovery node
- Check against max_retries before recovery
- If exceeded: force decision to "abort"

**Execute Recovery Node (src/workflow/nodes/execute_recovery.py):**

execute_recovery(state: dict) -> dict:
- Get recovery decision from state
- Increment state current_attempt
- Check if attempts >= max_retries:
  - If so: log warning, set decision to abort, return
- Based on decision:
  - retry-all: Clear resolutions, add failure context to resolver context
  - retry-specific: Filter resolutions to keep only ones not being retried, add failure context
  - bisect: Implement bisect logic (complex - see below)
  - switch-strategy: Update current_strategy and batch_size
- Reset conflicts_remaining to True (to re-enter resolution loop)
- Record attempt in attempt_history
- Return updated state

**Bisect Implementation:**

Bisect is complex and requires multiple test runs:
1. Divide resolutions into two halves
2. Apply first half, test
3. Apply second half, test
4. Identify which half(s) failed
5. Recursively bisect failing half
6. Eventually narrow down to specific problematic resolution(s)
7. Mark those for retry

For MVP, implement simplified bisect:
- Split resolutions in half
- Test first half only
- If fails: retry first half
- If succeeds: retry second half
- This is O(log N) builds but doesn't fully isolate (good enough for MVP)

**AttemptRecord Model (src/state/workflow.py):**

AttemptRecord:
- attempt_number: int
- strategy: str
- conflicts_resolved: int
- resolutions: list[ResolutionResult]
- build_result: BuildResult | None
- test_result: TestResult | None
- failure_summary: BuildFailureSummary | None
- recovery_decision: RecoveryDecision | None
- timestamp: datetime

### 20. Rewrite main.py to use LangGraph

Replace linear workflow with LangGraph execution.

**New main.py structure:**

Import LangGraph components (StateGraph, END)

Define main function:
- Load settings from config
- Setup logging based on verbosity
- Initialize all components:
  - CommandRunner with interactive flag
  - IMergeWrapper with workdir and imerge name
  - ToolRegistry and register all Layer 1 tools
  - Resolver with model config and tool registry
  - BuildRunner with workdir, build output_dir, and build timeout
  - TestRunner with workdir, test output_dir, and test timeout
  - Summarizer with model config
  - Planner with model config
- Build LangGraph workflow:
  - Create StateGraph with MergeWorkflowState schema
  - Add all nodes (initialize, plan_strategy, resolve_conflicts, build, test, summarize_failure, plan_recovery, execute_recovery, finalize)
  - Set entry point to initialize
  - Add simple edges (initialize to plan_strategy, plan_strategy to resolve_conflicts, resolve_conflicts to build, summarize_failure to plan_recovery, execute_recovery to resolve_conflicts, finalize to END)
  - Add conditional edges (build to after_build routing, test to after_test routing, plan_recovery to after_plan_recovery routing)
  - Compile the workflow
- Create initial state dict with:
  - source_ref, target_branch, workdir, imerge_name from settings
  - current_attempt: 0
  - Empty attempt_history list
  - conflicts_remaining: True
  - Empty resolutions list
  - status: "initialized"
  - All component instances
- Run workflow by invoking app with initial state
- Report results:
  - If status is "complete": log success with final commit SHA, exit with success code
  - Else: log error, log last failure root cause if available, exit with error code

**Key Points:**
- LangGraph manages state transitions
- Routing is declarative via conditional edges
- All logic is in nodes
- State is passed between nodes automatically
- Graph is compiled once, then invoked

### 21. Test full MVP

Comprehensive testing of the complete system.

**Test 1: Happy Path (No Failures)**

Setup: Simple merge with few conflicts, all resolutions correct
- Verify strategy selection works
- Verify all conflicts resolved
- Verify all builds pass
- Verify all tests pass
- Verify final merge commit created
- Check logs for complete audit trail

**Test 2: Single Failure with retry-all**

Setup: Introduce one incorrect resolution
- Verify build or test fails
- Verify summarizer identifies error
- Verify planner chooses retry-all
- Verify retry with failure context resolves correctly
- Verify second build and test pass

**Test 3: Multiple Failures with switch-strategy**

Setup: Use optimistic strategy, introduce errors
- Verify initial build or test fails
- Verify planner tries retry-all
- Verify retry fails again
- Verify planner switches to per-conflict strategy
- Verify per-conflict isolates and resolves issues

**Test 4: max_retries Exceeded**

Setup: Introduce persistent error that can't be auto-resolved
- Verify system attempts recovery up to max_retries
- Verify planner eventually chooses abort
- Verify system exits gracefully with clear error message
- Verify all attempts are logged

**Test 5: Different Strategies**

Test each strategy independently:
- Optimistic: Resolve all, build once, test once
- Batch (size=5): Resolve 5, build, test, repeat
- Per-conflict: Resolve 1, build, test, repeat

Verify each strategy executes correctly.

**Test 6: Recovery Strategies**

Test each recovery approach:
- retry-all: Works as expected
- retry-specific: Correctly identifies conflicts to retry
- bisect: Narrows down problematic resolution
- switch-strategy: Changes approach mid-merge

**Success Criteria:**
- All test scenarios pass
- No crashes or unhandled exceptions
- All decisions are logged with reasoning
- User can understand what happened from logs
- Final merge commits are valid
- git-imerge state is clean after completion

## Phase 7: Additional Investigation Tools

Goal: Add Layer 2 and Layer 3 tools for complex conflict resolution

### 22. Implement Layer 2 tools (git investigation)

These tools help LLM understand why changes were made.

**GitShowCommitTool (src/tools/git.py):**

Parameters:
- ref: str (commit SHA or ref like "HEAD", "FETCH_HEAD")
- file: str (optional - show changes only for this file)

Execution:
- Execute: git -C {workdir} show {ref} [-- {file}]
- Parse output to extract:
  - Commit SHA
  - Author and date
  - Commit message
  - Diff/changes
- Format as human-readable output with clear sections
- Truncate diff if very large (keep first/last 50 lines)

Output example format:
  Commit: abc123def456
  Author: John Doe <john@example.com>
  Date: 2024-01-15

  Message:
    Refactor: Move rematerialization logic to separate class

    The LiveRangeEdit class was becoming too complex. Extract
    rematerialization logic into new RematerializationAnalyzer class.

  Changes in llvm/include/llvm/CodeGen/LiveRangeEdit.h:
    At line 78: removed bool EnableRemat = true;
    At line 79: removed bool ScannedRemattable = false;

**GitLogTool (src/tools/git.py):**

Parameters:
- file: str (optional - log for specific file)
- max_count: int (default 10 - number of commits to show)

Execution:
- Execute: git -C {workdir} log --oneline --max-count={max_count} [-- {file}]
- Parse output into list of commits
- Format as readable list

Output example format:
  Recent commits for llvm/include/llvm/CodeGen/LiveRangeEdit.h:

    abc123d Refactor: Move rematerialization logic to separate class
    def456e Fix: Correct register allocation in edge case
    789abcd Update: Add support for new target architecture
    (and more...)

**ShowMergeSummaryTool (src/tools/merge.py):**

Parameters: none

Execution:
- Get merge info from git-imerge state
- Count total conflicts, resolved conflicts, remaining conflicts
- List affected subsystems/directories
- Format as overview

Output example format:
  Merge Summary:
    Source: heaven/main (1247 commits)
    Target: stable-test (423 commits)
    Total files with conflicts: 7
    Total conflict pairs: 12
    Conflicts resolved so far: 5
    Conflicts remaining: 7

    Affected areas:
      - llvm/include/llvm/CodeGen/ (4 conflicts)
      - llvm/lib/Target/MOS/ (3 conflicts)
      - llvm/tools/llvm-readobj/ (5 conflicts)

**ListAllConflictsTool (src/tools/merge.py):**

Parameters: none

Execution:
- Query git-imerge state for all conflict pairs
- For each pair, get conflicted files
- Format as structured list

Output example format:
  All conflicts in merge:

  Conflict pair 3-7:
    - llvm/include/llvm/CodeGen/LiveRangeEdit.h (2 conflicts in file)
    - llvm/include/llvm/CodeGen/RegisterCoalescer.h (1 conflict)

  Conflict pair 5-2:
    - llvm/lib/Target/MOS/MOSInstrInfo.cpp (1 conflict)

  (more conflict pairs...)

### 23. Implement Layer 3 tools (codebase search)

These tools help LLM search for information in the codebase.

**GrepCodebaseTool (src/tools/search.py):**

Parameters:
- pattern: str (regex pattern to search for)
- file_pattern: str | None (glob pattern to filter files, e.g., "*.cpp")
- context_lines: int (default 2 - lines of context around matches)

Execution:
- Execute: git -C {workdir} grep -n -C {context_lines} -E {pattern} [-- {file_pattern}]
- Parse output to extract matches with context
- Limit results to top 20 matches (to avoid overwhelming LLM)
- Format with file:line:content

Output example format:
  Found 15 matches for "EnableRemat" (showing first 20):

  llvm/lib/CodeGen/LiveRangeEdit.cpp:234:
    232:   // Check if rematerialization is enabled
    233:   if (EnableRemat && !ScannedRemattable) {
    234:     scanRemattable();
    235:   }

  llvm/lib/CodeGen/LiveRangeEdit.cpp:456:
    454: void LiveRangeEdit::scanRemattable() {
    455:   if (!EnableRemat) return;
    456:   // Scan for remattable instructions

  (more matches...)

**GrepInFileTool (src/tools/search.py):**

Parameters:
- file: str (specific file to search)
- pattern: str (regex pattern)
- context_lines: int (default 2)

Execution:
- Similar to GrepCodebaseTool but limited to one file
- Show all matches in file (no limit)
- Useful for examining specific file in detail

Output example format:
  Matches for "EnableRemat" in llvm/lib/CodeGen/LiveRangeEdit.cpp:

  Line 156:
    154:   // Initialize rematerialization
    155:   EnableRemat = true;
    156:   ScannedRemattable = false;

  Line 234:
    232:   // Check if rematerialization is enabled
    233:   if (EnableRemat && !ScannedRemattable) {
    234:     scanRemattable();

  (all matches in file...)

### 24. Register new tools and update resolver

**Update ToolRegistry initialization:**

In main.py tool setup:
- Create ToolRegistry instance
- Register Layer 1 core conflict tools:
  - ViewConflictTool with workdir
  - ViewMoreContextTool with workdir
  - ResolveConflictTool with workdir
- Register Layer 2 git investigation tools:
  - GitShowCommitTool with workdir
  - GitLogTool with workdir
  - ShowMergeSummaryTool with workdir and imerge instance
  - ListAllConflictsTool with imerge instance
- Register Layer 3 codebase search tools:
  - GrepCodebaseTool with workdir
  - GrepInFileTool with workdir

**Update Resolver prompt:**

Add to initial prompt:
Additional tools available:
- git_show_commit: See why a change was made (commit message and diff)
- git_log: See recent history of a file
- show_merge_summary: Overview of entire merge
- list_all_conflicts: See all conflicts in merge
- grep_codebase: Search for patterns across codebase
- grep_in_file: Search within a specific file

Use these tools when you need more context to make a decision.

### 25. Test with conflicts requiring investigation

Create test scenarios that benefit from additional tools.

**Test Scenario 1: Refactoring Conflict**

Setup: Upstream moved function to different file, fork modified the function
- Conflict: Function definition deleted in one branch, modified in other
- LLM should use git_show_commit to see "Moved to NewFile.cpp"
- LLM should use grep_codebase to find new location
- LLM should resolve by accepting deletion (function is elsewhere)

**Test Scenario 2: Variable Rename**

Setup: Upstream renamed variable, fork added new use of old name
- Conflict: Old variable name deleted, fork added code using old name
- LLM should use git_show_commit to see rename
- LLM should use grep_codebase to find new name
- LLM should resolve by updating fork's code to use new name

**Test Scenario 3: Conditional Feature**

Setup: Upstream deleted feature code, fork has MOS-specific usage
- Conflict: Feature code deleted upstream, fork uses it
- LLM should use grep_codebase to check if feature is used elsewhere in fork
- LLM should use git_log to see history of feature
- LLM should resolve by keeping fork's usage (MOS-specific)

**Success Criteria:**
- LLM correctly uses investigation tools when needed
- Tool usage is logged for observability
- Resolutions are more accurate with additional context
- LLM provides reasoning that references tool results

## Phase 8: Polish and Testing

Goal: Production-ready MVP

### 26. Add comprehensive logging

Ensure all decisions and actions are logged with full context.

**Areas to enhance:**

LLM Interactions:
- Log full prompt sent to each LLM at DEBUG level
- Log full response received at DEBUG level
- Log token counts for cost tracking
- Log response time for performance monitoring

git-imerge Operations:
- Log each git-imerge command executed
- Log git-imerge state transitions
- Log conflict detection and resolution
- Log finalization steps

Planner Decisions:
- Log strategy selection with full reasoning at INFO level
- Log recovery decisions with full reasoning at INFO level
- Include context that influenced decision
- Log alternatives considered

Tool Usage:
- Log every tool call with parameters
- Log tool results (truncated if very large)
- Track which tools are used most frequently
- Identify unused tools

Build and Test Results:
- Log build/test command and working directory
- Log build/test duration
- Log return code and success/failure
- Log path to log file for deep inspection

State Transitions:
- Log entry to each LangGraph node
- Log state changes within nodes
- Log routing decisions (which edge taken)
- Enable LangGraph's built-in debugging

**Log File Organization:**

splintercat.log:
- All DEBUG level logs
- Structured format with timestamps
- Rotation: 10MB per file
- Retention: 7 days

splintercat-decisions.log (NEW):
- Only INFO and above
- Human-readable summary of decisions
- No LLM prompts/responses (too verbose)
- Easy for humans to review what happened

**Log Format:**

Use structured logging with clear prefixes:
  2024-01-15 14:32:15 | INFO     | [Planner] Strategy selected: batch (size=10)
  2024-01-15 14:32:15 | INFO     | [Planner] Reasoning: Medium merge with ~50 conflicts...
  2024-01-15 14:32:45 | DEBUG    | [Resolver] Tool call: view_conflict(file="foo.cpp", conflict_num=1)
  2024-01-15 14:32:46 | DEBUG    | [Resolver] Tool result: (see conflict...)
  2024-01-15 14:33:12 | INFO     | [Resolver] Resolution: theirs (accept deletion)
  2024-01-15 14:33:12 | INFO     | [Resolver] Reasoning: Upstream moved function to bar.cpp

### 27. Add error handling

Handle all expected error cases gracefully with actionable messages.

**LLM API Errors:**

Rate limit (429):
- Retry with exponential backoff
- Log wait time
- Max 5 retries over 5 minutes
- If still failing: abort with clear message

Timeout (504/524):
- Retry with longer timeout
- Log that LLM is slow
- Max 3 retries
- If still failing: abort with suggestion to use faster model

Invalid API key (401):
- Immediate abort
- Clear message: "MODEL__API_KEY is invalid or missing"
- Show where to configure API key

Context too large (400 with "context_length" error):
- Attempt intelligent truncation of prompt
- Log warning about truncation
- Retry once
- If still failing: abort with message about file size

**git-imerge Errors:**

Unclean working tree:
- Detect with git status
- Abort immediately before starting imerge
- Message: "Working tree has uncommitted changes. Commit or stash them first."
- List specific files

imerge name already exists:
- Detect on start
- Abort with message: "git-imerge '{name}' already exists"
- Suggest: "Run 'git imerge remove {name}' or choose different name in config"

Merge conflict can't be applied:
- Rare git-imerge internal error
- Log full error from git-imerge
- Abort with message: "git-imerge encountered internal error"
- Suggest reporting issue with logs

**Build and Test Errors:**

Build or test timeout:
- Logged by BuildRunner or TestRunner
- Summarizer should detect timeout
- Planner should handle timeout differently (may be resource issue, not resolution error)
- Suggest: "Increase build.timeout or test.timeout in config if builds/tests are genuinely slow"

Build or test command not found:
- Detect early (before starting merge)
- Test build and test commands in Initialize node
- Abort if command doesn't exist
- Clear message: "Build/test command '{command}' not found"

Disk full during build or test:
- Detect from build/test output or error
- Abort with clear message
- Suggest: "Clear space in {output_dir}"

**File Operation Errors:**

Can't write resolved file:
- Permission denied: clear message, check file permissions
- Disk full: abort, suggest clearing space
- File locked: rare, suggest closing editors

Log directory doesn't exist:
- Create automatically in BuildRunner and TestRunner
- Log creation at DEBUG level

Config file not found:
- Abort with message: "config.yaml not found in current directory"
- Suggest: "Run from project root or specify config path"

**Error Message Principles:**

Every error message should include:
1. What went wrong (clear, non-technical language)
2. Why it probably happened (educated guess)
3. How to fix it (specific action to take)
4. Where to find more information (log file, docs)

Example format:
  ERROR: Build command not found

  The command 'ninja check-llvm' could not be executed.

  Possible causes:
    - Ninja is not installed
    - Build directory doesn't exist
    - Command path is incorrect in config.yaml

  To fix:
    1. Verify ninja is installed: which ninja
    2. Verify build directory exists: ls {target.workdir}/build
    3. Check config.yaml build.command setting

  For more details, see: splintercat.log

### 28. Documentation

Update all documentation to reflect implemented system.

**README.md updates:**

Usage section:
- Complete example of running splintercat
- Expected output at each stage
- Estimated time for large merges
- How to monitor progress

Configuration section:
- Document all config fields with examples
- Explain strategy options
- Explain recovery options
- Show environment variable overrides

Troubleshooting section:
- Common errors and solutions
- How to read logs
- When to abort and retry manually
- How to resume after fixing issues

**config.yaml updates:**

Add comprehensive inline comments:
- Explain every field
- Show example values
- Note defaults
- Link to relevant docs

**New doc: USAGE.md**

Create detailed usage guide:
- Prerequisites (git-imerge installed, API key, build environment)
- Step-by-step walkthrough
- What to expect at each phase
- How to interpret log output
- How to intervene if needed

**New doc: TROUBLESHOOTING.md**

Create troubleshooting guide:
- Common error messages with solutions
- How to debug LLM issues
- How to debug build and test issues
- How to debug git-imerge issues
- How to recover from partial merge
- How to report bugs with useful information

**Update design.md:**

Reflect implemented architecture:
- Update any design decisions that changed during implementation
- Document actual behavior vs. planned behavior
- Add lessons learned
- Add known limitations

**Update merge-resolver.md:**

Document implemented tools:
- List all Layer 1/2/3 tools
- Show example tool usage
- Explain how LLM uses tools
- Show example conversations

### 29. Real-world testing

Test with actual LLVM merge to validate MVP.

**Test Setup:**

Repository: llvm-mos
- Source: heaven/main (LLVM upstream)
- Target: stable-test (llvm-mos fork)
- Expected: approximately 1000+ commits, 10-50 conflicts

Configuration:
- Strategy: Let planner choose (likely batch)
- Model: Use production models (not cheap test models)
- Build: Fast incremental ninja build
- Test: Full ninja check-llvm (may take 30-60 min per test)
- Timeout: 14400 seconds (4 hours)

Preparation:
- Run reset-branches.bash to prepare clean state
- Verify build works before merge (baseline)
- Have adequate time (merge could take 8-24 hours)

**Monitoring:**

Watch for:
- Strategy selection and reasoning
- Resolution decisions and reasoning
- Build and test pass/fail patterns
- Recovery decisions if failures occur
- Tool usage patterns (which tools are used)
- Token/cost estimates

**Data Collection:**

Record:
- Total time taken
- Number of conflicts
- Number of builds and tests run
- Number of failures and recoveries
- LLM token usage (approximate cost)
- Which tools were most useful
- Which conflicts were hardest

**Success Criteria:**

Must achieve:
- Merge completes without human intervention
- Final build passes
- Final tests pass all checks
- Final merge commit has correct two-parent structure
- All decisions are explained in logs
- No crashes or hangs

Nice to have:
- Completes in reasonable time (under 24 hours)
- Cost is reasonable (under $50 in API calls)
- Most conflicts resolved correctly on first try
- Recovery strategies work when needed

**Post-Merge Validation:**

After merge completes:
- Run full test suite manually
- Compare with manual merge attempt (if available)
- Review decisions in logs for correctness
- Identify any incorrect resolutions
- Document lessons learned

**Failure Analysis:**

If merge fails (doesn't complete):
- Analyze where it got stuck
- Identify root cause (LLM, build, test, git-imerge, config)
- Determine if failure is fixable with config changes
- Determine if failure requires code changes
- Document findings

**Iteration:**

Based on results:
- Adjust prompts if LLM makes poor decisions
- Adjust config if timeouts or limits hit
- Fix bugs found during real-world use
- Improve error handling for issues encountered
- Update documentation with real-world insights

### 30. Performance and cost optimization (Post-MVP)

After successful real-world test, optimize for production use.

**LLM Cost Reduction:**

- Use cheaper models where possible (Resolver, Summarizer)
- Implement prompt caching for repeated contexts
- Reduce token usage in prompts (remove redundant text)
- Batch multiple small conflicts into one LLM call
- Consider local/self-hosted models for Resolver

**Build and Test Time Reduction:**

- Investigate incremental builds instead of full rebuilds
- Run subset of tests that are likely to catch errors
- Parallelize independent conflict resolutions
- Skip builds for trivial conflicts (whitespace, comments)
- Consider separate fast build check vs. full test validation

**Observability:**

- Add cost tracking (tokens, API calls, dollars)
- Add performance metrics (time per conflict, time per build/test)
- Add success rate tracking (resolutions correct on first try)
- Generate summary report at end of merge

**Reliability:**

- Add state persistence for resume capability
- Add checkpointing (can restart from last build/test)
- Add graceful shutdown (SIGINT handler)
- Add health checks (detect API issues early)

## MVP Scope Reminders

**Include in MVP:**
- Automatic conflict resolution with tool-based LLM architecture
- Three merge strategies (optimistic, batch, per_conflict) chosen by Planner
- Separate build validation (fast incremental) and test validation (complete test suite)
- LLM-driven strategic planning and recovery
- Multiple recovery strategies (retry-all, retry-specific, bisect, switch-strategy, abort)
- Complete merge to single commit via git-imerge
- Full logging of decisions and actions with reasoning
- Layer 1, 2, and 3 tools for conflict investigation

**Defer to post-MVP:**
- State persistence for resume capability (LangGraph supports this, just not implementing yet)
- Human-in-loop approval gates (fully automated for MVP)
- Cost tracking and optimization (basic logging only)
- Learning from historical patterns (no ML/memory)
- Resolution validation LLM (extra LLM pass before building/testing)
- Parallel conflict resolution (sequential only)
- Web UI (CLI only)
- CI/CD integration hooks
- Layer 4 (LSP) and Layer 5 (MCP/external) tools

## Implementation Notes

**Ordering Rationale:**

Phase 1-3: Prove the concept
- Get basic tool-based resolution working
- Validate with git-imerge workflow
- Test end-to-end with simple strategy

Phase 4-6: Add intelligence
- Failure detection (Summarizer)
- Strategic planning (Planner)
- Recovery orchestration (LangGraph)

Phase 7-8: Add capability and polish
- Investigation tools for complex conflicts
- Error handling and documentation
- Real-world validation

**Testing Strategy:**

Unit tests:
- Tool execution with mock files
- LLM response parsing with mock responses
- State transitions in isolation

Integration tests:
- Tool-based resolution with real LLM
- git-imerge workflow with test repo
- Build and test runners with real commands

End-to-end tests:
- Complete merge with Phase 3 simple flow
- Recovery scenarios with Phase 6 full system
- Real LLVM merge in Phase 8

**Common Pitfalls to Avoid:**

- Don't try to implement all tools at once - Layer 1 is sufficient for Phase 3
- Don't skip git-imerge testing - it's complex and needs validation early
- Don't skimp on logging - observability is crucial for debugging
- Don't ignore errors - handle gracefully with actionable messages
- Don't test only with perfect cases - introduce failures intentionally
- Don't rush to real LLVM merge - build up with simpler tests first

**When to Ask for Help:**

- LLM function calling isn't working as expected
- git-imerge state gets corrupted repeatedly
- Build or test timeouts are unavoidable even with large timeout
- Planner makes consistently poor decisions
- Recovery strategies don't actually recover
- Real merge hangs or crashes mysteriously

**Definition of Done for MVP:**

The MVP is complete when:
- Successfully merges llvm-mos heaven/main with no human intervention
- Final build passes
- Final tests pass all checks
- All decisions are logged and understandable
- Can handle and recover from build and test failures
- Documentation is complete and accurate
- Code is ready for other LLMs to extend and maintain
