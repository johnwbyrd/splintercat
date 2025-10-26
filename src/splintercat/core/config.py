"""Application state and configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import platformdirs
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from splintercat.core.base import BaseConfig, BaseState
from splintercat.core.log import Logger
from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource

# ============================================================
# TEMPLATE SUBSTITUTION NAMESPACE
# ============================================================

# Modules available for template substitution in YAML files
# Usage: {platformdirs.user_log_dir}, {os.getcwd}, {Path.cwd}
TEMPLATE_NAMESPACE = {
    'os': os,
    'platformdirs': platformdirs,
    'Path': Path,
}

# ============================================================
# CONFIG MODELS (loaded from YAML/env/CLI)
# ============================================================

class GitConfig(BaseConfig):
    """Git repository and merge configuration."""

    source_ref: str = Field(
        description=(
            "Branch, tag, or commit to merge from "
            "(e.g., 'main', 'v1.2.3')"
        )
    )
    target_workdir: Path = Field(
        description="Path to local git repository working directory"
    )
    target_branch: str = Field(
        description="Branch to merge into (e.g., 'stable', 'develop')"
    )
    imerge_name: str = Field(
        description="Unique name for this git-imerge operation"
    )
    imerge_goal: str = Field(
        default="merge",
        description=(
            "Merge structure: 'merge' (single commit), 'rebase', "
            "'rebase-with-history', or 'full'"
        ),
    )


class CheckConfig(BaseConfig):
    """Build and test validation configuration."""

    output_dir: Path = Field(
        description=(
            "Directory for storing check log files "
            "(supports {config.*} templates)"
        )
    )
    commands: dict[str, str] = Field(
        default_factory=dict,
        description="Named check commands (e.g., quick, normal, full)",
    )
    timeout: int = Field(
        default=3600,
        description="Timeout for checks in seconds (1 hour = 3600)",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts when checks fail",
    )


class LLMConfig(BaseConfig):
    """LLM provider and model selection."""
    model: str = Field(
        description=(
            "Model for conflict resolution. "
            "Format: 'provider:model' (e.g., openai:gpt-4o, "
            "openrouter/anthropic/claude-sonnet-4)"
        )
    )
    api_key: str | None = Field(
        default=None,
        description=(
            "API key for LLM provider. If not set, provider will "
            "look for provider-specific environment variables "
            "(e.g., OPENAI_API_KEY, OPENROUTER_API_KEY)"
        )
    )
    base_url: str | None = Field(
        default=None,
        description=(
            "Override API base URL for custom OpenAI-compatible endpoints "
            "(e.g., LocalAI at http://localhost:8080/v1)"
        )
    )





class Config(BaseConfig):
    """Application configuration loaded from YAML/env/CLI.

    This groups all configuration into logical sections.
    Inherits from BaseConfig to enable automatic cleanup cascade.
    """
    logger: Logger = Field(
        default=None,
        description="Logger configuration and runtime instance"
    )
    git: GitConfig = Field(
        description="Git repository and merge settings"
    )
    check: CheckConfig = Field(
        description="Build and test validation settings"
    )
    llm: LLMConfig = Field(
        description="LLM provider and model settings"
    )

    log_level: str = Field(
        default="info",
        alias="log-level",
        description=(
            "Console log level: 'trace', 'debug', 'info', "
            "'warn', 'error', 'fatal'"
        ),
    )
    interactive: bool = Field(
        default=False,
        description="Prompt before each command execution",
    )
    log_root: Path = Field(
        default_factory=(
            lambda: Path(platformdirs.user_state_dir()) / "splintercat"
        ),
        description=(
            "Root directory for all log files "
            "(supports {platformdirs.*} templates)"
        ),
    )

    # Command templates, prompts, and agent definitions
    commands: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description=(
            "Command templates organized by category "
            "(git, shell, custom, etc.)"
        ),
    )
    prompts: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="LLM prompt templates for resolver",
    )
    agents: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Agent configuration for resolver",
    )
    tools: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Platform-specific tool command definitions",
    )

    @model_validator(mode='after')
    def _setup_logger(self) -> 'Config':
        """Initialize global logger singleton after config loads.

        This is called automatically after all config is loaded and
        template substitution has occurred. It configures the global
        logger singleton using the logger config from YAML.
        """
        from splintercat.core.log import Logger, setup_logger

        # Create default logger config if not provided
        if self.logger is None:
            self.logger = Logger()

        # Initialize global singleton with config from YAML
        setup_logger(
            log_root=self.log_root,
            merge_name=self.git.imerge_name,
            console=self.logger.console,
            otlp=self.logger.otlp,
            file=self.logger.file,
            logfire=self.logger.logfire,

        )

        # Clean up bootstrap logger from yaml_settings
        # Safe: bootstrap and global logger are separate instances
        # with separate span processors
        from splintercat.core.yaml_settings import _cleanup_bootstrap_logger
        _cleanup_bootstrap_logger()

        return self

    def close(self):
        """Close config and global logger singleton.

        Overrides BaseCloseable.close() to also close the global logger.
        """
        # Close global logger singleton
        from splintercat.core.log import logger
        if logger is not None:
            logger.close()

        # Call parent close() to close other closeable children
        super().close()


# ============================================================
# RUNTIME STATE MODELS (mutable during workflow execution)
# ============================================================

class GlobalState(BaseState):
    """Global runtime state shared across all workflows."""
    pass


class MergeState(BaseState):
    """Merge workflow runtime state (mutates during execution)."""

    current_imerge: Any = Field(
        default=None,
        description="Active git-imerge object",
    )
    log_manager: Any = Field(
        default=None,
        description="Log manager instance",
    )
    iteration: int = Field(
        default=0,
        description="Current resolve-check iteration number",
    )
    status: str = Field(
        default="pending",
        description=(
            "Workflow status: pending, running, complete, failed"
        ),
    )
    conflicts_remaining: bool = Field(
        default=True,
        description="Whether unresolved conflicts remain",
    )
    conflicts_in_batch: list = Field(
        default_factory=list,
        description=(
            "Conflicts in current batch being resolved"
        ),
    )
    resolutions: list = Field(
        default_factory=list,
        description="History of successful resolutions",
    )
    last_failed_check: Any = Field(
        default=None,
        description="Most recent failed check result",
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries for current batch",
    )


    model_config = ConfigDict(arbitrary_types_allowed=True)


class ResetState(BaseState):
    """Reset workflow runtime state (mutates during execution)."""

    destroy_target_branch: bool = Field(
        default=False,
        description="Whether to destroy and recreate target branch",
    )
    merge_names_found: list[str] = Field(
        default_factory=list,
        description="Git-imerge operations found during cleanup",
    )
    total_refs_deleted: int = Field(
        default=0,
        description="Number of git refs deleted",
    )
    status: str = Field(
        default="pending",
        description="Reset status: pending, running, complete",
    )


class Runtime(BaseModel):
    """All runtime state organized by workflow.

    This groups runtime state into sections by workflow/command.
    Note: Runtime itself doesn't inherit from BaseState
    because it's the container, not a section.
    """
    global_: GlobalState = Field(
        default_factory=GlobalState,
        alias="global",
        description="Global state shared across all workflows"
    )
    merge: MergeState = Field(
        default_factory=MergeState,
        description="Merge workflow runtime state"
    )
    reset: ResetState = Field(
        default_factory=ResetState,
        description="Reset workflow runtime state"
    )


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

    config: Config = Field(
        description=(
            "Application configuration (from YAML/env/CLI)"
        )
    )
    runtime: Runtime = Field(
        default_factory=Runtime,
        description=(
            "Runtime state (mutates during workflow execution)"
        ),
    )
    include: list[str] | None = Field(
        default=None,
        description=(
            "Additional YAML files to include and merge. "
            "Use --include on CLI or include: in YAML files. "
            "Files are processed during load and deep-merged."
        ),
    )

    model_config = SettingsConfigDict(
        yaml_file="splintercat.yaml",
        env_file=".env",
        env_prefix="SPLINTERCAT_",
        env_nested_delimiter="__",
        cli_parse_args=True,
        cli_implicit_flags=True,
        cli_use_class_docs_for_groups=True,
        arbitrary_types_allowed=True,
        # Disregard .env variables that don't match config
        extra='ignore'
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
        2. YAML files with include support (defaults + config.yaml)
        3. .env file
        4. Environment variables
        5. File secrets
        """
        return (
            init_settings,
            YamlWithIncludesSettingsSource(settings_cls),
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    @model_validator(mode="after")
    def substitute_templates(self) -> "State":
        """Substitute template variables in all string fields
        recursively.

        Supports templates like {config.git.target_workdir} which
        will be replaced with the actual value from the state.

        This recursively walks the entire State object and
        substitutes templates in strings, Paths, dict values,
        and list items.
        """
        self._substitute_recursive(self)
        return self

    def _substitute_recursive(self, obj: Any) -> None:
        """Recursively substitute templates in all string/Path
        fields.

        Args:
            obj: Object to process (BaseModel, dict, list, or
                primitive)
        """
        if isinstance(obj, BaseModel):
            # Process all fields in the model
            for field_name in obj.__class__.model_fields:
                value = getattr(obj, field_name)
                new_value = self._substitute_value(value)
                if new_value is not value:
                    setattr(obj, field_name, new_value)
        elif isinstance(obj, dict):
            # Process dict values
            for key in obj:
                obj[key] = self._substitute_value(obj[key])
        elif isinstance(obj, list):
            # Process list items
            for i in range(len(obj)):
                obj[i] = self._substitute_value(obj[i])

    def _substitute_value(self, value: Any) -> Any:
        """Substitute templates in a single value.

        Args:
            value: Value to process

        Returns:
            Processed value with templates substituted
        """
        if isinstance(value, str):
            return self._substitute_string(value)
        elif isinstance(value, Path):
            return Path(self._substitute_string(str(value)))
        elif isinstance(value, (BaseModel, dict, list)):
            self._substitute_recursive(value)
            return value
        else:
            return value

    def _substitute_string(self, value: str) -> str:
        """Replace {field.path} templates with actual field
        values.

        Args:
            value: String possibly containing {field.path}
                templates

        Returns:
            String with templates replaced by actual values

        Examples:
            "{config.git.target_workdir}/build"
            → "/home/user/repo/build"
            "{platformdirs.user_log_dir}"
            → "~/.local/state/splintercat/log"
        """
        def replace_template(match):
            field_path = match.group(1)
            parts = field_path.split(".")

            # Check if first part is a module from TEMPLATE_NAMESPACE
            if parts[0] in TEMPLATE_NAMESPACE:
                obj = TEMPLATE_NAMESPACE[parts[0]]
                parts = parts[1:]  # Skip module name
            else:
                obj = self

            try:
                for part in parts:
                    obj = getattr(obj, part)

                # If resolved object is callable, call it
                if callable(obj):
                    obj = obj('splintercat', appauthor=False)

                return str(obj)
            except (AttributeError, TypeError):
                # Not a valid reference, leave unchanged
                return match.group(0)

        return re.sub(r'\{([a-z._]+)\}', replace_template, value)


# Export
__all__ = ["State", "BaseConfig", "BaseState"]
