# The Rice Theorem Problem in Merge Conflict Research

## Introduction

Current merge conflict benchmarks claim to measure "correctness" by comparing automated resolutions to human-produced resolutions. This document explains why this approach is fundamentally flawed and what should be measured instead.

## Rice's Theorem

Rice's Theorem (1951) states: For any non-trivial semantic property of programs, no algorithm can decide whether an arbitrary program has that property.

A semantic property is "non-trivial" if some programs have it and some don't. Examples: "program halts", "program sorts correctly", "program preserves intended behavior after merge".

**Implication for merge conflicts**: "This merge is correct" is a semantic property. It asks whether the merged program preserves the intended behavior of both branches. By Rice's Theorem, this is undecidable in the general case.

## What This Means for Merge Resolution

There is no unique "correct" merge for a given conflict. Instead, there exists a set (potentially infinite) of resolutions that:
1. Compile without errors
2. Pass existing tests
3. Preserve intended behavior from both branches
4. Meet any additional requirements

A merge conflict resolution is **acceptable** if it belongs to this set. It is not required to match any particular human-produced resolution.

## How Current Benchmarks Fail

### ConflictBench (180 Java scenarios)
**Claims**: 180 merging scenarios with "labeled true/false conflicts" and "developers' resolution strategies" as ground truth.

**Problem**: Treats one human's resolution as THE correct answer. If your tool produces different code that also compiles and passes tests, you're marked wrong.

**What they measure**: Edit distance or textual similarity to human resolution.

**What they should measure**: Does it compile? Do tests pass?

### ConGra (44,948 conflicts)
**Claims**: "Large-scale multilingual conflict resolution dataset" with conflicts "categorized based on code operations and complexity levels."

**Problem**: Evaluates by comparing to human resolution in the repository history. Assumes human got it right and there's only one right answer.

**What they measure**: Whether LLM output matches what the human committed.

**What they should measure**: Whether LLM output produces working software.

### GitGoodBench (900 samples from JetBrains)
**Claims**: Benchmark for evaluating merge conflict resolution with "easy/medium/hard" difficulty ratings.

**Problem**: No build systems or test suites included. Can only measure syntactic validity and textual similarity to provided resolution.

**What they measure**: Does output look like the example resolution?

**What they should measure**: Does output compile and pass tests in the actual project?

## Why Textual Similarity Is the Wrong Metric

Consider this conflict:
```
<<<<<<< ours
result = calculate_discount(price, 0.1)
=======
result = calculate_discount(price, customer.discount_rate)
>>>>>>> theirs
```

**Human resolution**: Keep theirs (use customer discount rate)

**Alternative resolution**: Keep ours (use fixed 10% discount)

**Academic benchmark**: Marks alternative as WRONG (doesn't match human)

**Reality**: Both might be correct depending on requirements:
- If requirement is "honor customer discount", human is right
- If requirement is "promotional 10% discount", alternative is right
- If tests pass either way, both are acceptable

The benchmark has no way to know which is correct. It just measures textual match to human choice.

## The Infinite Set Problem

For any non-trivial conflict, there are many textually distinct resolutions that are semantically equivalent:

```python
# Resolution 1
if condition:
    return value

# Resolution 2
return value if condition else None

# Resolution 3
result = value if condition else None
return result
```

A benchmark based on textual similarity will mark two of them wrong. But they're all correct.

Academic benchmarks optimize for matching one specific syntactic form, not for semantic correctness.

## What "Correct" Actually Means

Since "correct merge" is undecidable, we need approximations. The question is: which approximations are useful?

**Bad approximation** (current benchmarks):
- Textual similarity to one human resolution
- Assumes human is correct and unique
- Penalizes valid alternatives
- Optimizes for wrong objective

**Good approximations** (practical tests):
1. **Compiles**: No syntax or type errors
2. **Passes tests**: Existing test suite passes
3. **Meets requirements**: New functionality works as intended
4. **No regressions**: Doesn't break existing behavior

These are still approximations (tests can't prove correctness), but they're the RIGHT approximations. They measure properties we actually care about: working software.

## Implications for Published Research

### Claims of "95% Accuracy" Are Meaningless

When papers claim "our tool achieves 95% accuracy on ConflictBench", they mean:
- "95% textual similarity to how one human resolved these conflicts"

This does NOT mean:
- "95% of resolutions compile"
- "95% of resolutions pass tests"
- "95% of resolutions preserve intended behavior"

The accuracy number measures the wrong thing.

### Tools Optimized for Benchmarks May Perform Worse

If you train an LLM to maximize textual similarity to human resolutions in ConflictBench:
- It learns to mimic human patterns
- Including human mistakes
- Excluding valid alternatives humans didn't try
- Performance on benchmark improves
- Performance on real merges may degrade

**Goodhart's Law**: "When a measure becomes a target, it ceases to be a good measure."

### Benchmarks Without Build Systems Are Incomplete

GitGoodBench provides conflict scenarios but no:
- Build systems (Makefile, CMakeLists.txt, build.gradle)
- Test suites
- Dependency specifications
- Compilation targets

You cannot determine if a resolution is correct without these. You can only measure syntactic validity and textual similarity.

This is like evaluating a compiler by checking if its output "looks like" assembly code, rather than running the assembly and checking if it works.

## The Correct Approach

### Incremental Validation

The only practical way to evaluate merge correctness:
1. Apply resolution
2. Run build
3. Run tests
4. If failure, try different resolution with error context
5. Repeat until success or max retries

**Success metric**: Tests pass
**Failure metric**: Build fails or tests fail
**Improvement metric**: Success rate on real merges

### Why This Works

- Sidesteps Rice's Theorem by using approximation (tests)
- Measures property we care about (working software)
- Allows multiple valid resolutions
- Provides feedback for iterative improvement
- Matches real-world merge workflow

### Why Splintercat's Architecture Matters

Splintercat implements this approach:
1. git-imerge subdivides merge into small pieces
2. Resolve each conflict
3. Build and test incrementally
4. On failure, retry with error context
5. Success = all tests pass

This is theoretically grounded (avoids Rice's Theorem trap) and practically effective (measures what matters).

## Conclusion

Merge conflict research has been optimizing for the wrong objective function. By measuring textual similarity to human resolutions, benchmarks:
1. Assume unique ground truth where none exists (violates Rice's Theorem)
2. Penalize valid alternatives
3. Encourage overfitting to human patterns including mistakes
4. Ignore what actually matters: working software

The correct approach:
1. Accept that "correct merge" is undecidable
2. Use practical approximations: compiles, tests pass
3. Allow multiple valid resolutions
4. Measure improvement on real merges with real build systems

Splintercat's architecture (incremental merge + build validation + retry with error context) is grounded in this understanding. It doesn't try to match human text patterns. It tries to produce working software, validated by the only oracle that matters: the build system and test suite.

## References

- Rice, H. G. (1953). "Classes of recursively enumerable sets and their decision problems." Transactions of the American Mathematical Society, 74(2), 358-366.
- ConflictBench: Bowen Xu et al. (2024). "ConflictBench: A benchmark to evaluate software merge tools." Journal of Systems and Software.
- ConGra: HKU System Security Lab (2024). "ConGra: Benchmarking Automatic Conflict Resolution." https://github.com/HKU-System-Security-Lab/ConGra
- GitGoodBench: JetBrains Research (2025). "GitGoodBench: A Benchmark for Git Operations." https://github.com/JetBrains-Research/git-good-bench
