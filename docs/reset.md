# Git-imerge State Cleanup Guide

## The Problem

When git-imerge operations fail or are interrupted, they leave behind persistent state in the Git repository that can prevent future operations:

- **Lingering refs**: References under `refs/imerge/{merge_name}/` remain after failures
- **Test environment pollution**: Previous merge attempts block new test runs
- **State confusion**: Old imerge state can conflict with new merge attempts
- **Manual intervention required**: Standard git cleanup commands may not handle imerge-specific state

## Key Discoveries

### 1. Git-imerge State Persistence

Git-imerge creates extensive ref structures that persist even after merge failures:
```
refs/imerge/{merge_name}/state
refs/imerge/{merge_name}/manual/*
refs/imerge/{merge_name}/auto/*
```

These refs are **not** automatically cleaned up by:
- `git merge --abort`
- `git reset --hard`
- Standard git cleanup operations

### 2. Required Cleanup Process

To properly reset git-imerge state, you must:

**Discovery Phase:**
```bash
# Find all refs associated with a merge
git for-each-ref refs/imerge/{merge_name}/**
```

**Deletion Phase:**
```bash
# Option 1: Batch deletion (efficient)
git for-each-ref --format='delete %(refname)' \
  "refs/imerge/{merge_name}/**" | \
  git update-ref --stdin

# Option 2: Individual deletion
git for-each-ref refs/imerge/{merge_name}/** | \
  while read sha type ref; do
    git update-ref -d "$ref"
  done
```

**Verification:**
```bash
# Verify cleanup was successful
git for-each-ref refs/imerge/{merge_name}/**
# Should return nothing
```

## Proposed Solution: Reset Node

A **Reset** node that encapsulates this knowledge with appropriate safety:

### Design Principles

**User-initiated only**: Never automatic - requires explicit user action
- CLI command: `splintercat reset`
- Interactive prompt option in error recovery
- No workflow edges automatically route to Reset

**Safe by default**: Multiple validation layers
- Verify no active merge operations
- Check for unresolved conflicts
- Ensure not on scratch branches
- Show exactly what will be deleted

**Comprehensive cleanup**: Removes all imerge state
- Delete all refs under `refs/imerge/{merge_name}/`
- Use efficient batch deletion with `git update-ref --stdin`
- Update workflow state to reflect clean slate
- Verify successful cleanup

**Clear user communication**:
```
Found 47 refs for merge 'heaven-into-stable':
  refs/imerge/heaven-into-stable/state
  refs/imerge/heaven-into-stable/manual/0-0
  refs/imerge/heaven-into-stable/auto/0-1
  ...and 44 more
```
## When to Use Reset

### Appropriate scenarios:
- Failed merge with corrupted imerge state
- Stale merge attempt blocking new operations
- Test environment needs fresh start
- User explicitly wants to abandon current merge and start over

### Inappropriate scenarios:
- Automated error recovery (too destructive)
- During active merge operations
- Without user understanding of consequences
- As default fallback behavior

## Testing Considerations

After implementing Reset:
- Verify it cleans up all refs completely
- Test that multiple reset operations are safe
- Ensure it handles missing/partial state gracefully
- Validate all safety checks work correctly