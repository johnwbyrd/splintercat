"""Application state and configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

# ============================================================
# BASE CLASSES (semantic markers for readers)
# ============================================================

class BaseConfig(BaseModel):
    """Base class for all configuration sections.

    This is intentionally empty - it serves as a semantic marker
    to clearly indicate that a model represents configuration
    (loaded from YAML/env/CLI) rather than runtime state.
    """
    pass


class BaseState(BaseModel):
    """Base class for all runtime state sections.

    This is intentionally empty - it serves as a semantic marker
    to clearly indicate that a model represents runtime state
    (mutated during workflow execution) rather than configuration.
    """
    pass


# ============================================================
# CONFIG MODELS (loaded from YAML/env/CLI)
# ============================================================

class GitConfig(BaseConfig):
    """Git repository and merge configuration."""
    source_ref: str
    target_workdir: Path
    target_branch: str
    imerge_name: str
    imerge_goal: str = "merge"


class CheckConfig(BaseConfig):
    """Check execution configuration."""
    output_dir: Path
    default_timeout: int = 3600
    commands: dict[str, str] = Field(default_factory=dict)


class LLMConfig(BaseConfig):
    """LLM provider and model selection."""
    api_key: str
    base_url: str
    resolver_model: str
    summarizer_model: str
    planner_model: str


class StrategyConfig(BaseConfig):
    """Merge strategy and recovery configuration."""
    max_retries: int = 5
    available: list[str] = Field(
        default=["optimistic", "batch", "per_conflict"]
    )
    default_batch_size: int = 10


class Config(BaseModel):
    """Application configuration loaded from YAML/env/CLI.

    This groups all configuration into logical sections.
    Note: Config itself doesn't inherit from BaseConfig because
    it's the container, not a section.
    """
    git: GitConfig
    check: CheckConfig
    llm: LLMConfig
    strategy: StrategyConfig
    verbose: bool = False
    interactive: bool = False


# ============================================================
# RUNTIME STATE MODELS (mutable during workflow execution)
# ============================================================

class GlobalState(BaseState):
    """Global runtime state shared across all workflows."""
    current_command: str = ""


class MergeState(BaseState):
    """Merge workflow runtime state.

    This tracks the state of the merge workflow as it progresses.
    """
    current_imerge: Any = None
    status: str = "pending"
    conflicts_remaining: bool = True
    conflicts_in_batch: list = Field(default_factory=list)
    attempts: list = Field(default_factory=list)
    resolutions: list = Field(default_factory=list)
    current_strategy: str = ""
    check_results: list = Field(default_factory=list)
    last_failed_check: Any = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ResetState(BaseState):
    """Reset workflow runtime state.

    This tracks the state of the reset operation.
    """
    force: bool = False
    merge_names_found: list[str] = Field(default_factory=list)
    total_refs_deleted: int = 0
    status: str = "pending"


class Runtime(BaseModel):
    """All runtime state organized by workflow.

    This groups runtime state into sections by workflow/command.
    Note: Runtime itself doesn't inherit from BaseState because
    it's the container, not a section.
    """
    global_: GlobalState = Field(default_factory=GlobalState, alias="global")
    merge: MergeState = Field(default_factory=MergeState)
    reset: ResetState = Field(default_factory=ResetState)


# ============================================================
# STATE (config + runtime combined)
# ============================================================

class State(BaseSettings):
    """Complete application state - configuration and runtime.

    This is THE state object that flows through all workflows.

    Structure:
    - config: Configuration loaded from YAML/env/CLI (immutable)
    - runtime: Runtime state mutated during workflow execution

    The State object is a pydantic BaseSettings, which means:
    - It can load from YAML files
    - It can load from environment variables
    - It can load from CLI arguments
    - It can be serialized/deserialized (for persistence)
    - It validates all data on load
    """

    config: Config
    runtime: Runtime = Field(default_factory=Runtime)

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        env_file=".env",
        env_nested_delimiter="__",
        cli_parse_args=True,
        arbitrary_types_allowed=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings source priority.

        Priority order (highest to lowest):
        1. init_settings (direct instantiation arguments)
        2. YAML file (config.yaml)
        3. .env file
        4. Environment variables
        5. File secrets
        """
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    @model_validator(mode="after")
    def substitute_templates(self) -> "State":
        """Substitute template variables in string fields.

        Supports templates like {config.git.target_workdir} which will
        be replaced with the actual value from the state.

        This allows config values to reference other config values,
        e.g., check.output_dir can reference git.target_workdir.
        """
        # Substitute in check output_dir
        output_dir_str = str(self.config.check.output_dir)
        output_dir_substituted = self._substitute_string(output_dir_str)
        self.config.check.output_dir = Path(output_dir_substituted)

        return self

    def _substitute_string(self, value: str) -> str:
        """Replace {field.path} templates with actual field values.

        Args:
            value: String possibly containing {field.path} templates

        Returns:
            String with templates replaced by actual values

        Example:
            "{config.git.target_workdir}/build"
            → "/home/user/repo/build"
        """
        def replace_template(match):
            field_path = match.group(1)
            parts = field_path.split(".")

            # Navigate through nested fields starting from self
            obj = self
            for part in parts:
                obj = getattr(obj, part)

            return str(obj)

        return re.sub(r'\{([a-z._]+)\}', replace_template, value)


# Export
__all__ = ["State", "BaseConfig", "BaseState"]
