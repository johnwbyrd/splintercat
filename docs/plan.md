# Splintercat Coordinator Implementation Plan

## Executive Summary

Replace the current hardcoded strategy system with an intelligent Coordinator LLM that orchestrates per-conflict merge workflow. Remove batching concepts entirely. Always validate after each conflict resolution. Coordinator maintains continuity while each resolver gets fresh context.

## Goals

- **Intelligent Orchestration**: Replace hardcoded routing with LLM-based workflow decisions
- **Per-Conflict Workflow**: Resolve one conflict, validate, repeat (no batching)
- **Fresh Resolution Context**: Each conflict gets a dedicated, isolated resolver agent
- **Continuous Validation**: Always check after resolving conflicts
- **Proven Before Complex**: Validate current MVP before adding coordinator complexity

## Current Architecture Assessment

### Working Components
- LLM resolver with workspace tools ✅
- Git-imerge integration ✅
- Basic configuration system ✅
- Per-conflict resolution capability ✅
- Build validation with retry logic ✅

### Problematic Components
- Strategy abstraction (batch/optimistic/per-conflict) ❌ (premature complexity)
- Batching logic ❌ (unnecessary complexity)
- Hardcoded workflow routing ❌ (not adaptive)
- Mixed AI/non-AI decision making ❌ (inconsistent)

### Untested Components
- Real merge scenarios ❓
- Strategy effectiveness ❓
- Error recovery ❓

## Proposed Architecture

### Workflow Pattern

```
Initialize → Coordinator → Check → ResolveConflict → Coordinator → Check → ResolveConflict → ... → Finalize
```

**Key: Always check first in every cycle**

### Agent Roles

**Coordinator**
- Persistent LLM agent with full merge memory
- Analyzes state and chooses next action
- Learns from check results and conflict patterns
- Limits: Can choose check levels, decide on conflicts, handle failures

**Resolver**
- Fresh agent instance per conflict pair
- Focused solely on current conflict resolution
- Access to workspace investigation tools
- No inheritance of previous resolver contexts

### Node Behavior

**Coordinator Node**: Analyzes state → Returns specialized node
**Specialized Nodes**: Do their work → Always return to Coordinator
**Finalize Node**: Does work → Returns End (terminal)

### Configuration Changes

Remove `strategy.*` configs, keep safety limits for coordinator (if needed).
Add coordinator model selection eventually.

## Implementation Phases

### Phase 1: Remove Strategy Complexity (1 week)

**Simplify to proven per-conflict workflow**

1. Delete `src/splintercat/strategy/` (5 files)
2. Remove `StrategyConfig` from `config.py`
3. Update `initialize.py` to create no strategy objects
4. Modify `resolve_conflicts.py` to resolve 1 conflict, always return `Check`
5. Modify `Check` to always return `ResolveConflicts` or `Finalize` (no batch concept)
6. Update tests and remove strategy references

**Result**: Clean per-conflict workflow: resolve 1 → check → resolve 1 → check → ...

### Phase 2: Coordinator Agent (2-3 weeks)

**Add intelligent routing between nodes**

1. Create `src/splintercat/model/coordinator.py`
   - Pydantic-ai Coordinator agent with decision tools
   - Methods: `get_merge_status()`, `get_conflict_preview()`, `run_checks()`, `resolve_conflicts()`, `finalize_merge()`, `handle_failure()`

2. Create `src/splintercat/workflow/nodes/coordinator.py`
   - Coordinator node that decides next action
   - Persistent state across merge operations

3. Update workflow nodes:
   - `Check`: Remove routing logic, always return `Coordinator()`
   - `ResolveConflicts`: Remove routing logic, always return `Coordinator()`
   - Add coordinator to workflow graph

4. First implementation: Simple rule-based coordinator (no LLM yet)
   ```
   Always resolve next conflict if conflicts remain
   Always run 'quick' checks
   If check fails: request manual intervention
   ```

5. Add basic coordinator config (same model as resolver initially)

### Phase 3: Intelligent Coordinator (1-2 weeks after Phase 2)

**Upgrade to LLM-based decision making**

1. Implement full LLM coordinator with tools
2. Prompt: Analyze state, choose intelligent actions
3. Add risk assessment heuristics (path patterns for check levels)
4. Coordinator learns patterns (e.g., "IR files passed quick check before")

### Phase 4: Optimization & Safety (1 week)

**Bound the coordinator agents**

1. Add safety constraints (max conflicts per batch, min check frequency)
2. Intelligent check level selection (full for risky, quick for safe)
3. Enhanced failure handling with diagnostic integration

## Technical Specifications

### Coordinator Agent Interface

```python
class CoordinatorAgent:
    def __init__(self, config, state):
        self.history = []  # Check results, decisions made
        self.state = state

    @tool
    def get_merge_status(self) -> dict:
        """Get overall merge progress and recent history"""
        return {
            "total_conflicts": len(state.conflicts),
            "resolved": len(state.resolutions),
            "last_check_result": self.last_check,
            "check_history": self.history[-5:],  # Recent patterns
        }

    @tool  
    def get_conflict_preview(self, count=1) -> list[dict]:
        """Peek at next N conflicts with metadata"""
        return [{
            "files": ["lib/IR/Types.h", "lib/IR/Constants.cpp"],
            "estimated_risk": "high",  # Based on path patterns
            "last_commit_context": commit_info,
        }]

    @tool
    def decide_check_level(self, current_state) -> str:
        """Choose appropriate validation level"""
        if risk_high or first_check:
            return "full"
        elif confidence_high:
            return "quick"
        else:
            return "normal"

    @tool
    def should_continue(self, last_check_result) -> dict:
        """Decide next action based on validation result"""
        if last_check_result.success and conflicts_remain():
            return {"next": "resolve_conflict", "count": 1}
        elif last_check_result.success and not conflicts_remain():
            return {"next": "finalize"}
        else:
            return {"next": "handle_failure", "reason": analyze_failure}
```

### Node Interaction

```python
class Coordinator(BaseNode[State]):
    def __init__(self):
        self.agent = CoordinatorAgent()

    async def run(self, ctx) -> BaseNode:
        # Coordinator analyzes state
        decision = await self.agent.decide_next_action(ctx.state)

        # Return appropriate specialized node
        if decision["next"] == "run_checks":
            return Check(levels=[decision["check_level"]])

        elif decision["next"] == "resolve_conflict":
            return ResolveConflicts()

        elif decision["next"] == "finalize":
            return Finalize()

        elif decision["next"] == "handle_failure":
            return HandleFailure(decision["context"])

class Check(BaseNode[State]):
    async def run(self, ctx) -> BaseNode:
        # Do validation work
        result = await run_checks(self.check_names, ctx)
        ctx.state.update_last_check(result)

        # Always return to coordinator for next decision
        return Coordinator()

class ResolveConflicts(BaseNode[State]):
    async def run(self, ctx) -> BaseNode:
        # Do resolution work (always exactly 1 conflict in this design)
        await resolve_next_conflict(ctx)

        # Always return to coordinator for decision about checking
        return Coordinator()
```

## Success Criteria

### MVP Validation (Phase 0)
- ✅ Successful merges on test repositories
- ✅ LLM resolver works with real conflict scenarios
- ✅ Per-conflict rhythm functions correctly
- ✅ No critical bugs in current implementation

### Coordinator Implementation (Phases 1-4)
- ✅ Coordinator provides better routing than hardcoded logic
- ✅ Check level selection improves over time with learning
- ✅ Memory persists across operations without context bloat
- ✅ Fresh resolver contexts prevent contamination
- ✅ Failure handling improved with coordinated diagnostics

### Performance Goals
- No degradation from current per-conflict performance
- 10-20% improvement in merge success rate
- Similar or faster execution time
- No increase in LLM API costs

## Risk Mitigation

### Progressive Implementation
- Remove strategy complexity FIRST, validate remaining system
- Add basic coordinator SECOND, ensure workflow works
- Add LLM intelligence THIRD, isolates AI risk
- Add safety bounds LAST, prevents runaway behavior

### Fallback Options
- **Strategy removal fails**: Revert to current batch strategy
- **Coordinator too complex**: Keep coordinator but use rule-based decisions
- **LLM routing fails**: Add user override options for coordinator decisions

### Testing Strategy
- **Unit tests**: Each node and agent independently
- **Integration tests**: Full workflow with mock LLM responses
- **Real merge tests**: End-to-end with actual git conflicts
- **Regression tests**: Ensure no degradation from current system

## Follows llm.md Principles

✅ **YAGNI**: Doesn't implement coordinator until proven need exists
✅ **Design First**: Detailed plan before coding
✅ **Prove It Works**: Validates MVP before complexity
✅ **Simple Code**: Per-conflict rhythm, minimal abstractions
✅ **No Speculation**: Only adds intelligence when evidence shows benefit
✅ **User-Configured**: Eventually configurable coordinator model/limits

This plan provides evolutionary enhancement with clear fallback points and validates each step before proceeding to increased complexity.
