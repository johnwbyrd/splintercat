# Splintercat TODO

## Immediate Next Steps

1. Test basic functionality with small patch count
2. Fix any bugs that emerge
3. Test with full llvm-mos patch set

## Phase 2: BisectStrategy

- Implement BisectStrategy class
- Test bisection logic with small patch sets
- Compare performance vs Sequential

## Phase 3: Database Persistence

- Add SQLite database
- Persist attempt history across runs
- Track success/failure patterns by author, file, time
- Skip known-bad patches

## Phase 4: Smart Filtering

- Add filter/reorder capabilities to PatchSet
- Implement author-based filtering
- Implement file-based grouping
- Look-ahead: try later patches to fix earlier failures

## Phase 5: LLM Rewriting

- Integrate LLM API for patch rewriting
- Add LazyPatchSet for generated patches
- Cache rewrites in database
- Only rewrite high-value patches

## Phase 6: ML Prediction

- Train model on historical data
- Predict patch success probability
- Reorder patches by predicted success

## Future Ideas

- Parallel application in separate branches
- Dependency analysis (file overlap detection)
- Custom strategies (time-based, author-trust, etc.)
