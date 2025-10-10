# TODO: Splintercat Implementation

## Immediate Next Steps

### Phase 2: Tool-Based Resolver

1. **Implement Layer 1 conflict tools (src/tools/conflict.py)**
   - ViewConflictTool: Parse conflict markers, extract with context, format with line numbers
   - ViewMoreContextTool: Extended context viewing with explicit before/after line counts
   - ResolveConflictTool: Apply resolution (ours/theirs/both/custom), write file, stage with git

2. **Implement Resolver with function calling (src/model/resolver.py)**
   - Initialize LLM agent with tool registry
   - Build conversation loop with tool calling
   - Handle multi-turn conversations until ResolveConflictTool is called
   - Extract reasoning from conversation
   - Return ResolutionResult with decision and reasoning

### Phase 3: Strategy-Based Resolution

3. **Implement workflow nodes to use existing strategy classes**
   - Initialize node: Start git-imerge merge, verify success
   - Resolve conflicts node: USE strategy.should_build_now() to control batching loop
   - Build and test nodes: Use BuildRunner to execute commands
   - Finalize node: Call imerge.finalize(), get final merge commit

4. **Test end-to-end with simple merge**
   - Use llvm-mos repository with heaven/main merge
   - Verify conflict resolution, builds, tests, finalization
   - Document any issues found

### Phase 4: Failure Handling

5. **Implement Summarizer (src/model/summarizer.py)**
   - Read and intelligently truncate large log files
   - Extract root cause, error type, location, relevant excerpt
   - Return BuildFailureSummary

6. **Implement SummarizeFailure node**
   - Get BuildResult/TestResult with log file path
   - Call summarizer.summarize_failure()
   - Update state with failure_summary
   - Log summary for user visibility

7. **Test with intentional failures**
   - Compile error scenario
   - Test failure scenario
   - Link error scenario
   - Verify summarizer correctly identifies each type

### Phase 5: Recovery System

8. **Implement execute_recovery node**
   - Get recovery decision from state
   - Check attempts >= max_retries, abort if exceeded
   - Select appropriate recovery class (RetryAll/RetrySpecific/Bisect/SwitchStrategy)
   - Call recovery.execute(state) to apply recovery
   - Reset conflicts_remaining to True
   - Record attempt in history

9. **Implement Planner (src/model/planner.py)**
   - choose_initial_strategy(): Analyze merge scope, choose strategy, provide reasoning
   - plan_recovery(): Analyze failure, review attempts, choose recovery approach, provide reasoning

10. **Implement planning nodes**
    - PlanStrategy node: Build MergeContext, call planner, create strategy instance
    - PlanRecovery node: Build FailureContext, call planner, update state with decision

11. **Test planner in isolation**
    - Strategy selection with various merge contexts
    - Recovery planning with various failure contexts
    - Verify reasoning makes sense

### Phase 6: Graph Integration

12. **Complete all node implementations**
    - Ensure all nodes in src/workflow/nodes/ have working implementations
    - Verify nodes use strategy/recovery classes correctly
    - Test state transitions through graph

13. **Test full MVP**
    - Happy path (no failures)
    - Single failure with retry-all
    - Multiple failures with switch-strategy
    - max_retries exceeded scenario
    - Different strategies (optimistic, batch, per_conflict)
    - Different recovery strategies

### Phase 7: Additional Investigation Tools

14. **Implement Layer 2 git investigation tools (src/tools/git.py)**
    - GitShowCommitTool: Get commit details and diffs
    - GitLogTool: Show recent file history
    - ShowMergeSummaryTool: Overall merge statistics
    - ListAllConflictsTool: Current conflict frontier

15. **Implement Layer 3 search tools (src/tools/search.py)**
    - GrepCodebaseTool: Search across repository
    - GrepInFileTool: Search within specific file

16. **Update tool registry and resolver prompt**
    - Register Layer 2 and 3 tools
    - Update resolver prompt to explain additional tools

17. **Test with conflicts requiring investigation**
    - Refactoring conflict (moved function)
    - Variable rename conflict
    - Conditional feature conflict

### Phase 8: Polish and Testing

18. **Add comprehensive logging**
    - LLM interactions with token counts
    - git-imerge operations and state transitions
    - Planner decisions with full reasoning
    - Tool usage tracking
    - Build/test results with duration
    - State transitions and routing
    - Create splintercat-decisions.log for human-readable summary

19. **Add error handling**
    - LLM API errors (rate limit, timeout, invalid key, context too large)
    - git-imerge errors (unclean tree, name exists, internal errors)
    - Build/test errors (timeout, command not found, disk full)
    - File operation errors (permission denied, disk full, locked files)
    - Ensure all errors have clear messages with fix instructions

20. **Update documentation**
    - README.md: Usage, configuration, troubleshooting
    - config.yaml: Comprehensive inline comments
    - Create USAGE.md: Step-by-step walkthrough
    - Create TROUBLESHOOTING.md: Common errors and solutions
    - Update design.md: Reflect implemented architecture
    - Update merge-resolver.md: Document implemented tools

21. **Real-world testing with LLVM merge**
    - Setup: llvm-mos heaven/main → stable-test
    - Monitor: strategy selection, resolutions, failures, recoveries, tool usage
    - Collect data: time, conflicts, builds, failures, cost, tool usage patterns
    - Validate: merge completes, build passes, tests pass, correct structure
    - Analyze failures if any
    - Iterate based on results

22. **Performance and cost optimization (Post-MVP)**
    - LLM cost reduction (cheaper models, prompt caching, reduced tokens)
    - Build/test time reduction (incremental builds, test subsets)
    - Observability (cost tracking, performance metrics, success rates)
    - Reliability (state persistence, checkpointing, graceful shutdown)

## Known Issues

- All LLM model classes are skeleton implementations (pass statements)
- All workflow nodes are skeleton implementations (pass statements)
- All tool implementations return stub strings
- No state persistence for resume capability
- No cost tracking yet
- Tests are minimal (only BuildRunner has tests)

## Architecture Reminders

- Nodes are coordinators that USE strategy/recovery classes, don't reimplement logic
- Strategy classes control resolution batching via should_build_now()
- Recovery classes handle failures via execute()
- ToolRegistry provides all tools to LLM via function calling
- State flows through graph, nodes update it
- Pydantic AI Graph handles routing, nodes just implement logic
