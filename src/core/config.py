"""Configuration loading from YAML and command-line arguments."""

from pathlib import Path

from pydantic import BaseModel
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
    )
