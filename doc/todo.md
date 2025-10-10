# State Architecture Refactoring: Implementation Guide

## Purpose and Philosophy

This refactoring addresses a fundamental architectural issue: the confusion between "Settings" (which implies configuration) and "State" (which flows through workflows). By renaming and reorganizing, we make the codebase's intent explicit and align with pydantic-ai's mental model.

### Core Insight: Settings IS State

In pydantic-ai workflows, state is the data container that flows through nodes. For splintercat:
- Configuration (from YAML/env/CLI) is the INITIAL state
- Runtime data (imerge instances, status, resolutions) is MUTABLE state
- They coexist in the same object because they're both needed throughout execution
- This object should be called "State" not "Settings" to match workflow semantics

### Why This Matters

**Current confusion:**
- "Settings" implies read-only configuration
- But we mutate it during workflows (adding imerge instances, status)
- Code has `MergeWorkflowState` that embeds `Settings`, creating duplication
- Mental model is unclear: which is the "real" state?

**After refactoring:**
- "State" is explicitly the workflow state (both config and runtime)
- No embedding, no duplication
- Clear mental model: State flows through nodes, gets mutated
- Matches pydantic-ai documentation terminology

---

## Architectural Principles

### 1. Semantic Base Classes

We introduce `BaseConfig` and `BaseState` as empty base classes. This seems wasteful, but serves a critical purpose: **human readability**.

**Why empty base classes?**
- When a reader sees `class GitConfig(BaseConfig)`, they immediately know: "This is configuration"
- When they see `class MergeState(BaseState)`, they know: "This is runtime state"
- Without base classes, both would inherit from `BaseModel` - no semantic distinction
- The compiler doesn't care, but human readers do
- This is documentation through type hierarchy

**Analogy:** Like how we use `# Type hint` comments even though Python ignores them - they're for humans, not machines.

### 2. Logical Grouping of Configuration

Current config is flat and inconsistent:
- Some fields are wrapped in single-field objects (`SourceRef` just wraps `ref: str`)
- Others are nested (`BuildTestConfig` has multiple fields)
- No clear organization principle

**New approach:** Group by logical concern:
- `git`: Repository, branches, imerge settings (all git-related)
- `build`: Build/test execution (all build-related)
- `llm`: API keys, model selection (all LLM-related)
- `strategy`: Merge strategies, retries (all strategy-related)

**Why this matters:**
- Self-documenting: YAML structure shows what belongs together
- Extensible: Add `database`, `monitoring` sections later without refactoring
- Clear access patterns: `state.config.git.source_ref` reads like English
- Template substitution: `{config.git.target_workdir}` is clearer than `{target.workdir}`

**Trade-off:** More typing (`state.config.git.X` vs `state.git.X`), but much clearer semantics.

### 3. Config vs Runtime Separation

State contains two top-level sections:
- `config`: Everything loaded from YAML/env/CLI (immutable intent)
- `runtime`: Everything mutated during workflow execution

**Why separate?**
- **Serializability:** Can save/load just runtime state for resuming workflows
- **Clarity:** Nodes know if they're reading config or mutating runtime
- **Future-proofing:** Can add state persistence without mixing concerns

**YAML structure:**
```yaml
config:
  git: {...}
  build: {...}
  # All configuration here

# Future: runtime state can be saved/loaded
runtime:
  merge:
    status: resolving_conflicts
    # Resume from here
```

### 4. Runtime State Organization

Runtime state is organized by workflow:
- `runtime.global`: Shared across all workflows (current_command, etc.)
- `runtime.merge`: Merge workflow specific state
- `runtime.reset`: Reset workflow specific state

**Why by workflow?**
- Each workflow has different state needs
- No naming conflicts (merge.status vs reset.status)
- Easy to add new workflows (add `runtime.status: StatusState`)
- Clear ownership: merge nodes touch `runtime.merge`, not other sections

---

## CLI Integration Strategy

### Why Pydantic-Settings CLI?

**Eliminates boilerplate:**
- No manual argparse setup
- No manual YAML parsing
- No manual env var handling
- Pydantic-settings does it all via configuration

**Type-safe:**
- Config validation happens automatically
- CLI args are validated against pydantic models
- Wrong types fail fast with clear errors

**Subcommand pattern:**
```
splintercat merge          # Runs merge workflow
splintercat reset --force  # Runs reset workflow
splintercat status         # Future: check progress
```

### How It Works

**CliState:**
- Extends State (inherits all config loading)
- Adds subcommand fields (merge, reset)
- Implements `cli_cmd()` for dispatch

**Commands:**
- Each command is a `BaseModel` with parameters
- Has `run_workflow(state)` method
- Creates appropriate workflow and runs it

**Flow:**
```
User: splintercat merge
  ↓
pydantic-settings: Parse args, load YAML/env → CliState instance
  ↓
CliState.cli_cmd(): Get active subcommand → MergeCommand
  ↓
MergeCommand.run_workflow(state): Create workflow, run it
  ↓
Workflow executes with State flowing through nodes
```

**Key insight:** Commands are entry points, not workflows themselves. They create and run workflows.

---

## Implementation Details

### Template Substitution

Config values can reference other config values:
```yaml
config:
  git:
    target_workdir: /home/user/repo
  build:
    output_dir: "{config.git.target_workdir}/.splintercat/logs"
```

**Why?**
- DRY: Don't repeat paths
- Consistency: Change workdir in one place
- Flexibility: Users can customize without breaking relationships

**How it works:**
- `State` has `@model_validator` that runs after loading
- Finds `{config.path.to.field}` patterns
- Replaces with actual values
- Happens automatically before workflows run

### Environment Variable Overrides

Pydantic-settings supports nested env vars with delimiter:
```bash
export SPLINTERCAT__CONFIG__GIT__SOURCE_REF=feature/branch
export SPLINTERCAT__CONFIG__LLM__API_KEY=sk-xxx
```

**Why double underscore?**
- Single underscore is common in field names
- Double underscore unambiguously indicates nesting
- Configured via `env_nested_delimiter="__"`

**Hierarchy (highest to lowest priority):**
1. Direct instantiation args (for testing)
2. YAML file (config.yaml)
3. .env file
4. Environment variables
5. Defaults in models

### Node Access Patterns

**Old way (confusing):**
```python
settings = ctx.state.settings  # Why nested?
workdir = settings.target.workdir
ctx.state.imerge = imerge  # Why flat runtime state?
```

**New way (clear):**
```python
# Config access - reads initial configuration
workdir = ctx.state.config.git.target_workdir
command = ctx.state.config.build.command

# Runtime access - mutates workflow state
ctx.state.runtime.merge.current_imerge = imerge
ctx.state.runtime.merge.status = "initialized"
```

**Why this is better:**
- Path tells you what you're accessing (config vs runtime)
- Grouped by concern (git, build, merge)
- No confusion about where to find things

---

## Migration Strategy

### Why This Order?

1. **Create commands first** - Establishes new patterns without breaking old code
2. **Rewrite config.py** - Core change, but isolated
3. **Update entry point** - Small file, easy to verify
4. **Update workflow graph** - Infrastructure change
5. **Update nodes** - Bulk of changes, but mechanical search/replace
6. **Delete old files** - Clean up

**Rationale:** Build new alongside old, then cut over. Minimize time in broken state.

### Search/Replace Patterns

Most node changes are mechanical:
```
Find: from src.state.workflow import MergeWorkflowState
Replace: from src.core.config import State

Find: BaseNode[MergeWorkflowState]
Replace: BaseNode[State]

Find: ctx.state.settings.target.workdir
Replace: ctx.state.config.git.target_workdir

Find: ctx.state.imerge =
Replace: ctx.state.runtime.merge.current_imerge =
```

**Testing strategy:** Test imports after each phase to catch circular dependencies early.

---

## Rationale for Key Decisions

### Why Not Keep Settings Separate from State?

**Alternative considered:** Have `WorkflowState` that contains `settings: Settings`

**Why rejected:**
- Duplication: Same data in two places
- Confusion: Which is authoritative?
- Noise: `ctx.state.settings.config.git.X` is too deep
- Pydantic-ai doesn't require it: State can be anything

**Chosen approach:** Settings IS State. Config is just one section within it.

### Why YAML Root is `config:`?

**Alternative:** Keep flat YAML structure, just reorganize internally

**Why config root?**
- **Future state persistence:** Can add `runtime:` section to YAML for resume
- **Explicit:** No ambiguity about what's config vs what might be state
- **Standard pattern:** Many tools use config root (Kubernetes, etc.)

**Future capability:**
```yaml
config:
  # Load configuration

runtime:
  merge:
    status: resolving_conflicts
    # Resume from interrupted workflow
```

### Why Runtime State is Nested?

**Alternative:** Flat runtime fields directly on State

**Why rejected:**
- Naming conflicts: What if merge and reset both need "status"?
- Unclear ownership: Which workflow mutates what?
- Hard to extend: Adding new workflows pollutes State namespace

**Chosen approach:** Organize by workflow. Each workflow owns its section.

### Why Commands Have `run_workflow()` Method?

**Alternative:** Commands could just configure things, have framework run workflow

**Why rejected:**
- Commands need control: Some may not run workflows (status, etc.)
- Flexibility: Commands can do pre/post workflow work
- Explicit: Clear that command is responsible for workflow lifecycle

**Chosen approach:** Command creates workflow, runs it, returns exit code. Simple and explicit.

---

## Benefits of This Architecture

### Immediate Benefits

1. **Clarity:** Names match their purpose (State, not Settings)
2. **Type Safety:** Pydantic validates everything, including CLI args
3. **No Duplication:** One State object, not Settings + WorkflowState
4. **Self-Documenting:** Structure shows organization (git, build, merge)

### Future Benefits

1. **State Persistence:** Can serialize/deserialize State for resume
2. **Multiple Workflows:** Easy to add status, abort, continue commands
3. **Testing:** Can construct State with any config/runtime values
4. **Debugging:** Clear separation of config vs runtime state
5. **Evolution:** Add new config/runtime sections without breaking existing

### Developer Experience

**Before:** "Where do I put this field? Settings? State? Which one?"

**After:** "Is it config or runtime? Which workflow? Put it in the appropriate section."

**Before:** "Why is Settings called Settings if we mutate it?"

**After:** "It's State - of course we mutate it, that's what state is for."

---

## Testing Strategy

### Unit Tests

Test each piece in isolation:
- Config loading: Does State load from YAML correctly?
- Env overrides: Do env vars override YAML?
- Template substitution: Do templates expand correctly?
- CLI parsing: Do subcommands dispatch correctly?

### Integration Tests

Test combinations:
- Config + Runtime: Can we mutate runtime state?
- CLI + Workflow: Does `splintercat merge` actually run?
- State flow: Does State pass through nodes correctly?

### Manual Verification

Human checks:
- Does `python main.py --help` show subcommands?
- Are error messages clear when config is wrong?
- Does verbose mode actually show more output?

---

## Common Pitfalls

### Circular Imports

**Problem:** config.py imports commands, commands import State from config.py

**Solution:** Commands imported at END of config.py, after State definition

**Why:** Python's import system can handle this if done carefully

### Template Patterns

**Problem:** Template `{config.git.workdir}` fails to substitute

**Solution:** Ensure pattern matches `[a-z._]+` in regex, use lowercase with dots

**Why:** Template substitution is regex-based, case-sensitive

### Environment Variable Names

**Problem:** `SPLINTERCAT_CONFIG_GIT_SOURCE_REF` doesn't work

**Solution:** Use double underscore: `SPLINTERCAT__CONFIG__GIT__SOURCE_REF`

**Why:** Configured with `env_nested_delimiter="__"`

### Node Return Types

**Problem:** Returning class instead of instance: `return PlanStrategy`

**Solution:** Always return instance: `return PlanStrategy()`

**Why:** Pydantic-graph expects node instances, not classes

---

## Future Enhancements Enabled

### State Persistence

Save state to resume interrupted workflows:
```python
# Save
state.model_dump_json(file="saved-state.json")

# Load
state = State.model_validate_json(Path("saved-state.json").read_text())

# Resume workflow from saved state
workflow.run(start_node=Resume(), state=state)
```

### Additional Commands

Add status command easily:
```python
# 1. Create runtime state
class StatusState(BaseState):
    merge_info: dict = {}

# 2. Add to Runtime
class Runtime(BaseModel):
    status: StatusState = Field(default_factory=StatusState)

# 3. Create command
class StatusCommand(BaseModel):
    async def run_workflow(self, state: State) -> int:
        # Display state.runtime.merge info
        return 0

# 4. Add to CliState
class CliState(State):
    status: CliSubCommand[StatusCommand] = None
```

### Configuration Evolution

Add database config without breaking existing:
```python
class DatabaseConfig(BaseConfig):
    host: str
    port: int

class Config(BaseModel):
    git: GitConfig
    build: BuildConfig
    llm: LLMConfig
    strategy: StrategyConfig
    database: DatabaseConfig  # New section
```

Existing code unaffected because it accesses specific sections.

---

## Success Criteria

### Must Work

1. Config loads from YAML with new structure
2. CLI shows subcommands and help
3. `splintercat merge` runs workflow
4. `splintercat reset --force` cleans state
5. Template substitution works in build paths
6. Env vars override YAML values
7. All nodes can access config and runtime state

### Must Be Clear

1. Code readers understand config vs runtime
2. New developers can find where to add fields
3. Error messages guide users to fixes
4. YAML structure is self-explanatory

### Must Enable Future

1. Can add new commands without refactoring
2. Can add state persistence without rewriting
3. Can add new config sections cleanly
4. Can extend runtime state for new workflows

---

## Implementation Checklist

- [ ] Create `src/command/merge.py`
- [ ] Create `src/command/reset.py`
- [ ] Update `src/command/__init__.py`
- [ ] Rewrite `src/core/config.py` with new State structure
- [ ] Update `config.yaml` with config: root
- [ ] Rewrite `main.py` to use CliState
- [ ] Update `src/workflow/graph.py` state type
- [ ] Update `src/workflow/nodes/initialize.py`
- [ ] Update `src/workflow/nodes/plan_strategy.py`
- [ ] Update `src/workflow/nodes/resolve_conflicts.py`
- [ ] Update `src/workflow/nodes/build_test.py`
- [ ] Update `src/workflow/nodes/summarize_failure.py`
- [ ] Update `src/workflow/nodes/plan_recovery.py`
- [ ] Update `src/workflow/nodes/execute_recovery.py`
- [ ] Update `src/workflow/nodes/finalize.py`
- [ ] Update `src/workflow/nodes/reset.py`
- [ ] Check `src/state/*.py` files for old references
- [ ] Delete `src/app.py`
- [ ] Delete `src/state/workflow.py`
- [ ] Test config loading
- [ ] Test CLI dispatch
- [ ] Test node access patterns
- [ ] Test env var overrides
- [ ] Test template substitution

---

## Conclusion

This refactoring is not about adding features - it's about clarity. By aligning our code with pydantic-ai's mental model and making our intent explicit through naming and organization, we make the codebase maintainable and extensible.

The key insight is simple: State is state. It flows through workflows, gets mutated, contains both config and runtime data. Calling it "Settings" was confusing. Calling it "State" is honest.

Everything else follows from that truth.
