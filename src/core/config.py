"""Configuration loading from YAML and command-line arguments."""

import yaml
from pathlib import Path

from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Commands(BaseModel):
    """Git command templates."""

    fetch: str
    merge_base: str
    list_commits: str
    format_patch: str
    checkout: str | None = None
    get_state: str | None = None
    apply: str | None = None
    add: str | None = None
    commit: str | None = None
    rollback: str | None = None


class SourceConfig(BaseModel):
    """Source repository configuration."""

    repo: str
    branch: str
    workdir: Path
    commands: Commands


class TargetConfig(BaseModel):
    """Target repository configuration."""

    branch: str
    start_point: str
    workdir: Path
    commands: Commands


class Settings(BaseSettings):
    """Application settings loaded from YAML, env vars, and CLI args."""

    source: SourceConfig
    target: TargetConfig
    test_command: str
    interactive: bool = False
    verbose: bool = False

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        env_nested_delimiter="__",
        cli_parse_args=True,
    )

    @model_validator(mode="before")
    @classmethod
    def merge_git_defaults(cls, data):
        """Merge git command defaults from src/defaults/git.yaml."""
        defaults_path = Path(__file__).parent.parent / "defaults" / "git.yaml"

        if not defaults_path.exists():
            return data

        with open(defaults_path) as f:
            defaults = yaml.safe_load(f)

        if "commands" not in defaults:
            return data

        default_commands = defaults["commands"]

        # Merge commands for source
        if "source" in data:
            if "commands" not in data["source"]:
                data["source"]["commands"] = {}
            for key, value in default_commands.items():
                if key not in data["source"]["commands"] or not data["source"]["commands"][key]:
                    data["source"]["commands"][key] = value

        # Merge commands for target
        if "target" in data:
            if "commands" not in data["target"]:
                data["target"]["commands"] = {}
            for key, value in default_commands.items():
                if key not in data["target"]["commands"] or not data["target"]["commands"][key]:
                    data["target"]["commands"][key] = value

        return data
