# TODO: Splintercat Implementation

## Current Status

The architecture has been simplified to focus on a minimal viable product:
- Removed: Planner LLM, Summarizer LLM, complex recovery strategies
- Strategy selection is now deterministic (configured by user)
- Failure recovery is simple retry-with-error-context
- Single LLM model handles all conflict resolution

## Simplified Architecture

**Workflow**: Initialize → ResolveConflicts → Check → [retry or next batch or finalize]

**Components**:
- One LLM model (resolver)
- Three strategies (optimistic, batch, per_conflict) - user configured
- Simple retry mechanism with error context
- Four workflow nodes (Initialize, ResolveConflicts, Check, Finalize)

## Next Steps

### Phase 1: Implement Resolver (MVP Core)

1. **Implement conflict tools (src/tools/conflict.py)**
   - ViewConflictTool: Parse conflict markers, show with context
   - ResolveConflictTool: Apply resolution, stage with git

2. **Implement Resolver model (src/model/resolver.py)**
   - Initialize LLM with tool registry
   - Implement conversation loop with tool calling
   - Pass error context on retry (from last_failed_check)
   - Return resolution decision and reasoning

3. **Implement ResolveConflicts node**
   - Get conflicts from imerge.get_current_conflict()
   - Call resolver for each conflict
   - Respect strategy.should_check_now() for batching
   - Track conflicts in batch for retry purposes
   - Update conflicts_remaining from imerge state

### Phase 2: End-to-End Testing

4. **Test with real merge**
   - Use small merge (5-10 conflicts)
   - Verify: conflict resolution → check → finalize
   - Test retry on build failure
   - Measure: time, token cost, success rate

5. **Test strategy variations**
   - Optimistic: resolve all, check once
   - Batch (N=5): resolve 5, check, repeat
   - Per-conflict: resolve 1, check, repeat
   - Compare: speed vs debuggability tradeoff

### Phase 3: Investigation Tools (Add as Needed)

6. **Add git tools only if resolver fails without them**
   - GitShowCommitTool: View commit details
   - GitLogTool: View file history

7. **Add search tools only if resolver fails without them**
   - GrepCodebaseTool: Search repository
   - GrepInFileTool: Search within file

8. **Test: Do investigation tools improve success rate?**
   - Measure resolver accuracy with/without tools
   - Only keep tools that demonstrably help

### Phase 4: Polish

9. **Logging and observability**
   - Log LLM calls with token counts
   - Log resolution decisions with reasoning
   - Log strategy batch boundaries
   - Log retry attempts with error context

10. **Error handling**
    - LLM API errors (rate limit, timeout, invalid key)
    - git-imerge errors (unclean tree, name exists)
    - Check command errors (timeout, command not found)

11. **Documentation**
    - Update README with simplified architecture
    - Update design.md to match implementation
    - Update configuration.md with current fields
    - Add example splintercat.yaml configs

### Phase 5: Real-World Validation

12. **LLVM-MOS merge test**
    - Large merge (100+ commits, 20+ conflicts)
    - Measure: time, cost, success rate, human intervention
    - Identify failure modes
    - Iterate based on results

## Deferred Until Proven Necessary

These were removed as speculative complexity. Add back only with evidence:
- **Planner LLM**: Strategy selection is now user-configured
- **Summarizer LLM**: Pass raw error logs to resolver on retry
- **Complex recovery**: Only simple retry implemented
- **Multiple check levels**: Start with one check command

## Known Issues

- Resolver model is stub (pass statements)
- ResolveConflicts node is stub
- No tool implementations yet
- No tests beyond CheckRunner
- No cost tracking

## Architecture

- Initialize: Start imerge, create strategy from config
- ResolveConflicts: Call resolver until strategy says check
- Check: Run checks, on failure retry with error context
- Finalize: Call imerge.finalize() to create merge commit
