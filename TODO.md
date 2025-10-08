# Splintercat Implementation TODO

Implementation order for MVP, organized by phases.

## Phase 1: Core Infrastructure

Goal: Get basic plumbing working independently

1. **Update config.py** - Add configuration classes
   - Add `ModelConfig` class (api_key, base_url, resolver_model, summarizer_model, planner_model)
   - Add `BuildTestConfig` class (command, output_dir, timeout)
   - Add `IMergeConfig` class (name, goal)
   - Update `Settings` to include these new configs

2. **Implement git-imerge wrapper** (`src/git/imerge.py`)
   - `start_merge()` - initialize git-imerge
   - `get_conflicts()` - get list of conflicting commit pairs
   - `get_conflict_files()` - get files for a conflict pair
   - `finalize()` - simplify to single commit

3. **Implement BuildRunner** (`src/runner/build.py`)
   - `run_build_test()` - execute command, save logs to timestamped files, return BuildResult

4. **Test infrastructure independently**
   - Test git-imerge wrapper with real repository
   - Test BuildRunner with sample commands
   - Verify configs load correctly

## Phase 2: Model Resolver

Goal: Get conflict resolution working with model

5. **Implement Resolver** (`src/model/resolver.py`)
   - Initialize with model config (OpenRouter/LangChain)
   - `resolve_conflict()` - call model to resolve one conflict
   - Handle conflict markers, commit context, optional failure context

6. **Test resolver with manual examples**
   - Create sample conflicts
   - Verify model produces valid resolutions
   - Check conflict markers are removed

## Phase 3: Simple Linear Flow

Goal: End-to-end merge with fixed strategy, no intelligence

7. **Implement workflow nodes** (simple versions):
   - `initialize.py` - call git-imerge start
   - `resolve_conflicts.py` - loop through conflicts, call resolver for each
   - `build_test.py` - call build runner, return result
   - `finalize.py` - call git-imerge finalize

8. **Write simple main.py**
   - Load config
   - Setup logging
   - Hardcode "batch" strategy
   - Linear workflow: initialize → resolve all → build → finalize
   - No recovery - just fail on build errors with exit code

9. **Test end-to-end**
   - Use simple merge case (few commits, simple conflicts)
   - Verify complete flow works
   - Check final merge commit is created

## Phase 4: Failure Handling

Goal: Detect and report failures intelligently

10. **Implement Summarizer** (`src/model/summarizer.py`)
    - Initialize with model config
    - `summarize_failure()` - extract error info from build logs
    - Return BuildFailureSummary with structured data

11. **Implement SummarizeFailure node** (`src/workflow/nodes/summarize_failure.py`)
    - Call summarizer on failed build logs
    - Update state with failure summary

12. **Update main.py**
    - Add conditional: if build fails → summarize → report to user → exit
    - Log failure summary for debugging
    - Still no automatic recovery

13. **Test with intentional failures**
    - Create merge that will fail build
    - Verify summarizer extracts useful error info
    - Check user gets actionable feedback

## Phase 5: Strategic Planning

Goal: Model makes strategic decisions

14. **Implement Planner** (`src/model/planner.py`)
    - Initialize with model config
    - `choose_initial_strategy()` - pick strategy based on merge scope
    - `plan_recovery()` - decide recovery approach on failure

15. **Implement planning nodes**:
    - `plan_strategy.py` - call planner for initial strategy
    - `plan_recovery.py` - call planner for recovery decision

16. **Test planner in isolation**
    - Test strategy selection with various merge scenarios
    - Test recovery planning with different failure types
    - Verify planner returns valid decisions

## Phase 6: LangGraph Integration

Goal: Full MVP with state machine and recovery

17. **Implement LangGraph workflow** (`src/workflow/graph.py`)
    - Define state machine with all nodes
    - Implement routing logic:
      - BuildTest success → Finalize
      - BuildTest failure → SummarizeFailure
      - PlanRecovery routes based on decision (retry/bisect/switch-strategy/abort)
    - Handle retry loops with max_retries limit

18. **Rewrite main.py to use LangGraph**
    - Initialize workflow graph
    - Create initial state
    - Run workflow
    - Handle completion and errors

19. **Test full MVP**
    - Test happy path (no failures)
    - Test single failure with retry-all recovery
    - Test multiple failures with strategy switching
    - Test max_retries exceeded
    - Verify all recovery strategies work

## Phase 7: Polish and Testing

Goal: Production-ready MVP

20. **Add comprehensive logging**
    - Log all model prompts and responses
    - Log all git-imerge operations
    - Log all planner decisions with reasoning

21. **Add error handling**
    - Handle model API errors (retry with backoff)
    - Handle git-imerge errors (unclean working tree, etc)
    - Handle timeout errors

22. **Documentation**
    - Update README with usage examples
    - Document configuration options
    - Add troubleshooting guide

23. **Real-world testing**
    - Test with actual LLVM merge (1000+ commits)
    - Test with build failures
    - Test resume capability (if implemented)
    - Document results and learnings

## MVP Scope Reminders

**Include in MVP:**
- Automatic conflict resolution with model
- Three merge strategies (optimistic, batch, per_conflict)
- Build/test validation
- Model-driven strategic planning and recovery
- Multiple recovery strategies (retry-all, retry-specific, bisect, switch-strategy, abort)
- Complete merge to single commit
- Full logging of decisions and actions

**Defer to post-MVP:**
- Resume capability (state persistence)
- Human-in-loop approval gates
- Cost tracking
- Learning from historical patterns
- Resolution validation model
- Parallel conflict resolution
- Web UI
- CI/CD integration

## Notes

- Start with Tier 1 (Phase 1-3) to prove the concept works
- Add intelligence incrementally (Phase 4-6)
- Use synthetic conflicts for early testing, real merges for validation
- For initial recovery, implement retry-all and abort first
- Add bisect and retry-specific recovery strategies later if needed
