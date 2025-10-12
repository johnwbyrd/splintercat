"""Tests for YAML include: directive."""

from pathlib import Path

import pytest

from splintercat.core.config import State
from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


def test_minimal_config_loads(fixtures_dir):
    """Minimal config with no includes loads successfully."""
    # Override model_config for test
    yaml_file = fixtures_dir / "minimal.yaml"

    # Create settings source directly
    source = YamlWithIncludesSettingsSource(State, yaml_file=str(yaml_file))
    data = source()

    assert "config" in data
    assert data["config"]["git"]["source_ref"] == "test/branch"


def test_yaml_include_directive(fixtures_dir):
    """YAML include: directive loads and merges other file."""
    yaml_file = fixtures_dir / "with_include.yaml"

    source = YamlWithIncludesSettingsSource(State, yaml_file=str(yaml_file))
    data = source()

    # Should have both base config and included commands
    assert "config" in data
    assert "commands" in data["config"]
    assert "custom" in data["config"]["commands"]
    assert data["config"]["commands"]["custom"]["test_cmd"] == "echo custom"


def test_nested_includes(fixtures_dir):
    """File that includes another file with includes works."""
    yaml_file = fixtures_dir / "nested_include.yaml"

    source = YamlWithIncludesSettingsSource(State, yaml_file=str(yaml_file))
    data = source()

    # Should have loaded: nested_include -> with_include -> extra_commands
    assert "custom" in data["config"]["commands"]
    assert data["config"]["git"]["source_ref"] == "nested/branch"


def test_include_with_relative_path(fixtures_dir, tmp_path):
    """Include paths are resolved relative to including file."""
    # Create a subdirectory with config
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # Create a config in subdir that includes ../fixtures/extra_commands.yaml
    config_file = subdir / "config.yaml"
    config_file.write_text(f"""
include: ../fixtures/extra_commands.yaml

config:
  git:
    source_ref: relative/test
    target_workdir: /tmp/test
    target_branch: main
    imerge_name: test-merge
    imerge_goal: merge
  check:
    output_dir: /tmp/logs
    default_timeout: 300
    commands:
      quick: "echo test"
  llm:
    api_key: test-key
    base_url: https://test.com
    resolver_model: test/model
    summarizer_model: test/model
    planner_model: test/model
""")

    # Move fixtures to expected location
    import shutil
    fixtures_copy = tmp_path / "fixtures"
    shutil.copytree(fixtures_dir, fixtures_copy)

    source = YamlWithIncludesSettingsSource(State, yaml_file=str(config_file))
    data = source()

    # Should have loaded commands from relative path
    assert "custom" in data["config"]["commands"]


def test_include_removes_directive(fixtures_dir):
    """Include directive is removed from final data."""
    yaml_file = fixtures_dir / "with_include.yaml"

    source = YamlWithIncludesSettingsSource(State, yaml_file=str(yaml_file))
    data = source()

    # include: should not appear in final data
    assert "include" not in data


def test_multiple_includes_in_yaml(fixtures_dir, tmp_path):
    """YAML with multiple include: entries loads all files."""
    config_file = tmp_path / "multi.yaml"
    config_file.write_text(f"""
include:
  - {fixtures_dir / 'extra_commands.yaml'}
  - {fixtures_dir / 'override_strategy.yaml'}

config:
  git:
    source_ref: multi/test
    target_workdir: /tmp/test
    target_branch: main
    imerge_name: test-merge
    imerge_goal: merge
  check:
    output_dir: /tmp/logs
    default_timeout: 300
    commands:
      quick: "echo test"
  llm:
    api_key: test-key
    base_url: https://test.com
    resolver_model: test/model
    summarizer_model: test/model
    planner_model: test/model
""")

    source = YamlWithIncludesSettingsSource(State, yaml_file=str(config_file))
    data = source()

    # Should have custom commands from extra_commands.yaml
    assert "custom" in data["config"]["commands"]
    # Should have overridden strategy from override_strategy.yaml
    assert data["config"]["strategy"]["max_retries"] == 99
    # Should have overridden git command from override_strategy.yaml
    assert "git log --graph" in data["config"]["commands"]["git"]["log"]
