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

**File-Based Workspace System**
- ConflictWorkspace class: Creates /tmp/conflict_xyz/ directories
- Conflict parsing: Extract base.txt, ours.txt, theirs.txt from hunks
- Context extraction: before.txt and after.txt (both required)
- FileMetadata: Track content, description, line_count, required flag

**Workspace Tools (src/tools/conflict.py)**
- list_files(): Show available files with descriptions and line counts
- read_file(name, start_line, end_line): Read file with line numbers
- write_file(name, content, description): Create new workspace files
- cat_files(input_files, output_file): Concatenate files in order
- submit_resolution(filename): Validate and apply resolution to git

**Resolver Model (src/model/resolver.py)**
- Initialize LLM client (OpenAI/OpenRouter API)
- Bind workspace tools to LLM for function calling
- Implement conversation loop with tool execution
- Parse YAML decision format from LLM responses
- Pass error context on retry (from last_failed_check)
- Apply submitted resolution and stage with git

**ResolveConflicts Node Implementation**
- Get conflicts from imerge.get_current_conflict()
- For each file with conflicts, parse hunks into sections
- Create ConflictWorkspace for each hunk
- Initialize resolver with workspace tools
- Execute resolution conversation loop
- Respect strategy.should_check_now() for batching
- Track conflicts in batch for retry purposes
- Update conflicts_remaining from imerge state

### Phase 2: End-to-End Testing

**Test with Real Merge**
- Use small merge (5-10 conflicts)
- Verify complete workflow: Initialize → ResolveConflicts → Check →
  Finalize
- Test retry on build failure with error context
- Measure: time, token cost, success rate
- Inspect workspace files in /tmp after resolution

**Test Strategy Variations**
- Optimistic: resolve all conflicts, check once
- Batch (N=5): resolve 5 conflicts, check, repeat
- Per-conflict: resolve 1 conflict, check immediately, repeat
- Compare: speed vs debuggability tradeoff

**Optional: Validation Tools Enhancement**
- Add build() tool: Test compilation without submitting resolution
- Add test() tool: Run tests without submitting resolution
- Measure: Do they improve accuracy for complex merges?
- Only keep if demonstrably helpful (YAGNI principle)

### Phase 3: Investigation Tools (Add as Needed)

Core workspace tools (list, read, write, cat, submit) are sufficient
for basic conflict resolution. Investigation tools help the LLM
understand intent and impact of changes. Add only when resolver fails
without them.

**Git Investigation Tools**
- git_show_commit(ref, file): View commit message and changes
- git_log(file, max_count): View recent commit history
- show_merge_summary(): Overview of entire merge operation
- list_all_conflicts(): List all conflict hunks in merge
- Add only if resolver fails without commit context

**Codebase Search Tools**
- grep_codebase(pattern, file_pattern, context): Search repository
- grep_in_file(file, pattern, context): Search within specific file
- Add only if resolver needs to find related code

**Measure Impact**
- Test resolver accuracy with/without investigation tools
- Only keep tools that demonstrably improve success rate
- Track token costs - investigation tools add context

### Phase 4: Polish

**Logging and Observability**
- Log LLM calls with token counts and costs
- Log resolution decisions with reasoning from YAML
- Log strategy batch boundaries
- Log retry attempts with error context
- Log workspace file operations (created, concatenated, submitted)
- Preserve workspace directories for post-mortem analysis

**Error Handling**
- LLM API errors (rate limit, timeout, invalid key, malformed
  response)
- git-imerge errors (unclean tree, name exists, invalid state)
- Check command errors (timeout, command not found, non-zero exit)
- Workspace errors (invalid file concatenation, missing required
  files)
- Validation errors (resolution doesn't include before/after context)

**Documentation**
- Update README with file-based workspace approach
- Update design.md to reflect implemented architecture
- Update configuration.md with all current config fields
- Add example splintercat.yaml configs for different use cases
- Document workspace file format and tool usage patterns

### Phase 5: Real-World Validation

**LLVM-MOS Merge Test**
- Large merge (100+ commits, 20+ conflicts)
- Use batch strategy with appropriate batch size
- Measure: total time, LLM token costs, success rate, human
  intervention needed
- Identify failure modes and patterns
- Analyze workspace artifacts from failed resolutions
- Iterate based on empirical results

## Deferred Until Proven Necessary

These were removed as speculative complexity. Add back only with evidence:
- **Planner LLM**: Strategy selection is now user-configured
- **Summarizer LLM**: Pass raw error logs to resolver on retry
- **Complex recovery**: Only simple retry implemented
- **Multiple check levels**: Start with one check command

## Known Issues

- Resolver model is stub (pass statements only)
- ResolveConflicts node is stub (doesn't call resolver)
- ConflictWorkspace class not implemented
- Workspace tools not implemented (list_files, read_file, write_file,
  cat_files, submit_resolution)
- Conflict hunk parsing not implemented (extract base/ours/theirs from
  git markers)
- No LLM client integration
- No tests beyond CheckRunner
- No cost tracking (tokens, API calls, dollars)
- No LLM token usage logging
- Workspace directory cleanup not implemented

## Architecture

- Initialize: Start imerge, create strategy from config
- ResolveConflicts: Call resolver until strategy says check
- Check: Run checks, on failure retry with error context
- Finalize: Call imerge.finalize() to create merge commit
