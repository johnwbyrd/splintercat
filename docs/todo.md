# Splintercat: TODO

## Current Status

MVP is functionally complete. Core workflow, LLM resolver, workspace tools, git integration, and configuration system are implemented and tested. Ready for real-world validation.

## What Needs to Be Done

### Immediate: End-to-End Validation

**Test on Real Merge**
- Set up small test merge (5-10 conflicts) in separate repository
- Run complete workflow: Initialize → ResolveConflicts → Check → Finalize
- Verify LLM successfully uses workspace tools to resolve conflicts
- Test retry mechanism with intentional build failure
- Measure execution time and identify bottlenecks
- Document any failures or edge cases discovered

**Validate All Three Strategies**
- Test optimistic strategy (resolve all, check once)
- Test batch strategy with N=5
- Test per-conflict strategy (check after each)
- Compare tradeoffs: speed vs isolation vs retry frequency

**Expected Outcomes**
- Identify missing features or edge cases
- Discover LLM tool usage issues
- Find gaps in error handling
- Validate that retry-with-error-context works
- Determine if investigation tools are needed

### If Real Testing Shows Need

**Token Cost Tracking**
- Add explicit tracking if logfire instrumentation insufficient
- Calculate cost per conflict, per merge
- Add cost limits and warnings

**Investigation Tools** (implement only if resolver fails without them)
- git_show_commit(ref, file): View commit details
- git_log(file, max_count): Recent history for context
- show_merge_summary(): Merge overview
- list_all_conflicts(): All hunks in merge
- grep_codebase(pattern): Search repository
- grep_in_file(file, pattern): Search specific file

**Better Error Messages**
- Distinguish LLM API errors from git errors from check errors
- Provide actionable remediation suggestions
- Better handling of malformed LLM responses

**Performance Optimization**
- If LLM context too large: implement smarter context windowing
- If conflict resolution slow: consider caching git operations
- If check commands timeout: add timeout configuration per check

### Documentation Updates

**README.md**
- Update status from "Resolver implementation in progress" to "Ready for testing"
- Add note about workspace approach (git workdir not /tmp)
- Update quick start with real example config

**design.md**
- Document actual workspace implementation vs original design
- Explain tool-based approach vs file extraction
- Update to match implementation reality

**Example Configs**
- Add example for LLVM-style large merge
- Add example for small library merge
- Add example with multiple check levels
- Document strategy selection guidance

### LLVM-MOS Production Test

**When Small Merges Work**
- Test on real LLVM-MOS merge (100+ commits, 20+ conflicts)
- Use batch strategy with tuned batch size
- Full logging and observability
- Measure: time, tokens, success rate, retry frequency
- Document systematic failures if any
- Identify patterns in conflict types and resolution quality

**Iterate Based on Results**
- Add investigation tools if patterns show they'd help
- Tune prompts based on resolution quality
- Adjust strategies based on retry patterns
- Document best practices for different merge scenarios

### Future Enhancements (Low Priority)

**User Experience**
- Progress indicators for long operations
- Interactive mode to review LLM decisions before applying
- Dry-run mode to preview without committing
- Better visualization of merge state

**Advanced Recovery**
- If simple retry insufficient: implement bisect recovery
- If batch sizes wrong: implement adaptive batch sizing
- If specific conflicts problematic: implement retry-specific recovery

**Multiple Check Levels**
- If single check inadequate: add quick/normal/full check levels
- Planner to choose appropriate check based on confidence
- Skip expensive checks when confidence high

## Not Planned (YAGNI)

These were removed as speculative. Only implement if evidence from real merges demonstrates need:

**Planner LLM**: Strategy selection is user-configured
**Summarizer LLM**: Raw error logs work for retry context
**Complex recovery strategies**: Simple retry first
**Automatic strategy switching**: User configures strategy
**ML/learning from history**: No evidence this helps yet

## Current Blockers

**None.** System is ready for real-world testing. Next step is running actual merges to discover what needs improvement.

## Design Decisions

### Workspace Uses Git Workdir

LLM operates directly on git working directory where conflicts exist, not extracted files in /tmp. Simpler and allows git commands for investigation.

### Investigation Tools Deferred

Core 6 workspace tools sufficient for basic resolution. Investigation tools (git_show_commit, grep, etc.) add complexity and token cost. Only implement when evidence shows they improve success rate.

### Simple Retry Mechanism

Pass error log to resolver on failure. Let LLM learn from errors. More complex recovery (bisect, switch-strategy) only if this proves insufficient.

### User-Configured Strategy

User chooses optimistic/batch/per-conflict based on merge size and risk tolerance. No LLM planner needed - it's a straightforward engineering tradeoff.
