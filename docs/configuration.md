# Configuration

## Introduction

Splintercat is designed to be completely flexible. Almost every behavior can be overridden—git commands, LLM prompts, agent parameters, check strategies, recovery logic. This flexibility exists because different projects have different needs, and those needs change as projects evolve.

The configuration system is built on composition. You start with sensible defaults that ship with the package. You override only what matters for your project. You can share common settings across projects using includes. You can separate secrets from checked-in configuration. You can experiment with different settings without touching your base configuration.

Everything in splintercat is configurable. Git operations are defined as command templates you can override. LLM prompts that guide conflict resolution are stored in YAML files you can modify. Agent behavior—which tools are available, temperature settings, token limits—lives in configuration. Check commands, recovery strategies, batch sizes, timeout values: all configurable.

This document explains how the configuration system works, not what specific fields exist. Field definitions change as the project evolves. This explains the mechanisms you use to build and compose your configuration.

## How Configuration Loading Works

Splintercat loads configuration from multiple sources and merges them together. Later sources override earlier ones. The system is designed so defaults provide a working baseline, your project configuration adds specifics, and runtime overrides handle experiments and secrets.

Think of it as layers. The bottom layer is package defaults -- git commands, LLM prompts, agent settings -- that work for most projects. The next layer is your config.yaml file where you specify your repository, branches, and check commands. Above that are include files for shared settings. Then environment variables for secrets and CI/CD overrides. Finally, CLI arguments for one-off changes.

When the same setting appears in multiple layers, the top layer wins. But only that specific setting is overridden—everything else from lower layers is preserved. If defaults define ten strategy parameters and you override one, the other nine remain. This is deep merging: only what you explicitly change gets changed.

The loading order matters because it determines precedence:

**Package defaults** - Lowest priority. These ship with Splintercat in src/splintercat/defaults/. They define git command templates, LLM prompts, agent configurations, and strategy parameters. You never modify these directly. They update when you upgrade Splintercat.

**User config** - Your personal configuration that applies across all projects. This is where you put your LLM model preferences, API settings, and other personal defaults. Splintercat looks for this in a platform-specific location:
- Linux: ~/.config/splintercat/splintercat.yaml
- macOS: ~/Library/Application Support/splintercat/splintercat.yaml
- Windows: %LOCALAPPDATA%\splintercat\splintercat.yaml

This file is optional. If it doesn't exist, Splintercat continues without it.

**Project config** - Configuration specific to the current project or repository. This is where you specify which branches to merge, repository paths, and project-specific check commands. Splintercat looks for splintercat.yaml in your current directory.

This file is optional. If it doesn't exist, Splintercat continues without it.

**Include files** - Additional YAML files loaded via include: directives in your YAML files or --include CLI arguments. These let you share configuration across projects or organize large configurations into manageable pieces. Includes are processed in order, each overriding the previous.

**.env file** - Environment variable definitions loaded from .env in your current directory. Use this for API keys and other secrets you don't want to check into version control. Variables use the format SPLINTERCAT_CONFIG__SECTION__KEY=value where the SPLINTERCAT_ prefix identifies them as belonging to this application, and double underscores separate nesting levels.

**Environment variables** - Variables set in your shell environment. Use the same format as .env files: SPLINTERCAT_CONFIG__SECTION__KEY=value. Useful for CI/CD systems that inject configuration through environment variables.

**CLI arguments** - Highest priority. Command-line arguments like --config.verbose=true or --config.git.source_ref=main override everything else. Use these for one-off changes and experiments.

When you run splintercat merge, the system loads all these sources in order, deep-merging them together, and produces a single unified configuration. Template substitution happens after all sources are loaded. Then the workflow begins.

The key insight: you only specify what changes at each layer. Defaults provide comprehensive settings. User config overrides personal preferences. Project config overrides project-specific details. Include files override shared settings. Environment variables override secrets. CLI arguments override experimental changes. Each layer is minimal, changing only what matters at that level.

### User Config vs Project Config

Splintercat follows a common pattern: separate configuration for personal settings versus project settings.

User config contains settings that are the same regardless of which project you're working on. Put your LLM model preferences here, your default check commands, your personal workflow settings. This file lives in your user configuration directory and applies to all Splintercat operations you run.

Project config contains settings specific to this repository or merge operation. Put your source and target branches here, the repository path, project-specific build commands. This file lives in your project directory (typically under version control) and only applies when you run Splintercat from that directory.

Example user config (platform-specific location):
```yaml
config:
  llm:
    base_url: https://openrouter.ai/api/v1
    resolver_model: openai/gpt-4o-mini
    planner_model: anthropic/claude-sonnet-4
    summarizer_model: openai/gpt-4o-mini
  strategy:
    max_retries: 5  # Personal preference
```

Example project config (./splintercat.yaml):
```yaml
config:
  git:
    source_ref: upstream/main
    target_workdir: /home/user/llvm-mos
    target_branch: stable
    imerge_name: llvm-upstream-merge
  check:
    commands:
      quick: cd build && ninja check-llvm
```

This separation keeps secrets and personal preferences out of version control while letting project-specific settings be shared with the team.

## Composition Mechanisms

Three mechanisms let you build flexible configurations: includes for splitting configuration across files, deep merge for preserving unchanged settings, and templates for avoiding repetition.

### Includes

Includes let you split configuration across multiple files and compose them together. This is useful when you have settings shared across multiple projects, when your configuration gets large enough to organize into sections, or when you want to separate concerns like commands vs prompts vs agent settings.

Any YAML file can include other YAML files using the include: directive. Put include: at the top level of your YAML file with a list of files to include. Splintercat loads each included file and deep-merges its content with the including file.

Paths in include: directives are resolved relative to the file containing the directive. If config.yaml contains include: commands.yaml, Splintercat looks for commands.yaml in the same directory as config.yaml. Relative paths like ../shared/common.yaml work as expected. Absolute paths work too.

Included files can themselves include other files. This is recursive. Splintercat processes includes depth-first: when it encounters an include: directive, it immediately loads and processes that file (and any files it includes) before continuing with the rest of the including file.

The system detects circular includes and raises an error. If a.yaml includes b.yaml and b.yaml includes a.yaml, Splintercat stops and reports the circular dependency.

You can also load include files from the command line using --include. This is useful for overriding settings without modifying your base config.yaml. CLI includes have higher priority than YAML includes but lower priority than other CLI arguments.

Example scenario: You maintain several projects that all merge from the same upstream. You create a shared configuration file with common git command templates and LLM prompts. Each project's config.yaml includes that shared file and adds project-specific settings like repository path and branch names. When you improve a prompt, all projects get the improvement automatically.

### Deep Merge

When multiple configuration sources define overlapping settings, Splintercat merges them intelligently. This is called deep merging. The goal is to let you override only what you need to change while preserving everything else.

Deep merge works recursively through nested structures. If defaults define config.strategy with three fields and you override config.strategy.max_retries in your config.yaml, the other two fields from defaults are preserved. Your override replaces only that specific field, not the entire strategy section.

This means you can specify minimal configuration at each layer. Defaults provide comprehensive settings. You override only the handful of values that differ for your project. Include files override only shared settings. CLI arguments override only experimental values. Each layer is sparse, defining only what changes.

Without deep merge, you would need to repeat every field from defaults in your config.yaml even if you only want to change one value. With deep merge, you specify only what changes.

Exception: lists are replaced entirely, not merged. If defaults define a list with three items and you override it with a list containing one item, the result is your one-item list. Lists do not merge element-by-element. If you want to add to a default list, you must repeat all the items you want to keep plus your new items.

This list behavior exists because merging lists is ambiguous. Should the lists concatenate? Should items be unique? Should matching items merge? Different use cases need different behaviors. Rather than guess, Splintercat uses simple replacement: your list replaces the default list entirely.

### Templates

Templates let you avoid repetition in configuration files. Splintercat supports two distinct types of templates that substitute at different times.

Config reference templates substitute during configuration loading. These let you define a value once and reference it elsewhere. The syntax is {config.section.key} where the path after config. navigates through your configuration structure. When Splintercat loads your configuration, it replaces these templates with the actual values from your config.

Example: You define your repository path as config.git.target_workdir. You want your check output directory to be a subdirectory of that path. You write config.check.output_dir: "{config.git.target_workdir}/.splintercat/logs". During loading, Splintercat replaces the template with the actual path, and your output_dir becomes /full/path/to/repo/.splintercat/logs.

Config reference templates let you define values once and reuse them. Change the base value, and all references update automatically. This eliminates duplication and keeps configuration maintainable.

Runtime parameter templates substitute during command execution. These are placeholders in command strings that get filled in when the command runs. The syntax is {simple_name} where the name is a simple identifier like workdir, ref, or count.

Example: The default git log command is defined as git -C {workdir} log --oneline -n {count}. This is a template string. When Splintercat needs to run this command, it substitutes {workdir} with the actual repository path and {count} with the desired number of commits. The same template is used many times with different values.

Runtime parameter templates remain as {name} in the loaded configuration. They are not substituted during loading. They are substituted each time the command executes. This is intentional. The same command template is used repeatedly with different parameters.

How to distinguish the two types: config reference templates always start with config. and use dots to navigate nested structure. Runtime parameter templates are simple names without dots. Config reference templates substitute once during loading. Runtime parameter templates substitute many times during execution.

If a config reference template cannot be resolved because the path does not exist or has a typo, it remains as {config.unknown.field} in the output. This is visible when you examine the loaded configuration, which helps debugging. Runtime parameter templates also remain as {name} if not substituted, which is normal—they are meant for later substitution during execution.

Templates compose well with includes and deep merge. You can define base paths in one file, reference them in another file, include both files, and the templates resolve correctly. Config reference templates are substituted after all includes are processed and all sources are merged. Runtime parameter templates are never substituted during loading, regardless of includes or merge order.

Config reference templates work with values from any source, including environment variables. If you set SPLINTERCAT_CONFIG__LLM__API_KEY as an environment variable or in a .env file, that value becomes available as config.llm.api_key. You can then reference it elsewhere in your YAML using {config.llm.api_key}. This is useful for secrets: define them once via environment variables, never put them in YAML files, but reference them in computed values if needed. The environment variable provides the value, pydantic loads it into the configuration structure, and config reference templates let you use it wherever you need it.
