"""Configuration loading from YAML and command-line arguments."""

import re
from pathlib import Path

from pydantic import BaseModel, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class SourceRef(BaseModel):
    """Source git reference to merge from."""

    ref: str


class TargetConfig(BaseModel):
    """Target repository configuration."""

    workdir: Path
    branch: str


class ModelConfig(BaseModel):
    """Model (LLM) configuration."""

    api_key: str
    base_url: str
    resolver_model: str
    summarizer_model: str
    planner_model: str


class BuildTestConfig(BaseModel):
    """Build and test validation configuration."""

    command: str
    output_dir: Path
    timeout: int


class IMergeConfig(BaseModel):
    """git-imerge configuration."""

    name: str
    goal: str


class MergeConfig(BaseModel):
    """Merge strategy and recovery configuration."""

    max_retries: int
    strategies_available: list[str]
    default_batch_size: int


class Settings(BaseSettings):
    """Application settings loaded from YAML, env vars, and CLI args."""

    source: SourceRef
    target: TargetConfig
    build_test: BuildTestConfig
    model: ModelConfig
    imerge: IMergeConfig
    merge: MergeConfig
    verbose: bool = False
    interactive: bool = False

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        env_nested_delimiter="__",
        cli_parse_args=True,
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
        """Add YAML config source to settings sources."""
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            file_secret_settings,
        )

    @model_validator(mode="after")
    def substitute_templates(self) -> "Settings":
        """Substitute template variables like {target.workdir} in string fields."""
        # Substitute in build_test.command
        self.build_test.command = self._substitute_string(self.build_test.command)

        # Substitute in build_test.output_dir (Path type, convert to string and back)
        output_dir_str = str(self.build_test.output_dir)
        output_dir_substituted = self._substitute_string(output_dir_str)
        self.build_test.output_dir = Path(output_dir_substituted)

        return self

    def _substitute_string(self, value: str) -> str:
        """Replace {field.path} templates with actual field values.

        Args:
            value: String possibly containing {field.path} templates

        Returns:
            String with templates replaced by actual values
        """
        def replace_template(match):
            field_path = match.group(1)
            parts = field_path.split(".")

            # Navigate through nested fields
            obj = self
            for part in parts:
                obj = getattr(obj, part)

            return str(obj)

        # Find all {field.path} patterns and replace them
        return re.sub(r'\{([a-z._]+)\}', replace_template, value)
