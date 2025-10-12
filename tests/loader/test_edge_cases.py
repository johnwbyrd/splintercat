"""Tests for edge cases and error handling."""

from pathlib import Path

import pytest

from splintercat.core.config import State
from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


def test_circular_include_detected(fixtures_dir):
    """Circular include raises ValueError during initialization."""
    yaml_file = fixtures_dir / "circular_a.yaml"

    # Circular detection happens during __init__, not __call__
    with pytest.raises(ValueError, match="Circular include"):
        YamlWithIncludesSettingsSource(State, yaml_file=str(yaml_file))


def test_missing_include_file_raises_error(fixtures_dir, tmp_path):
    """Missing include file raises FileNotFoundError."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
include: nonexistent.yaml

config:
  git:
    source_ref: test/branch
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

    # Missing include file raises error (current behavior)
    # This is probably the right behavior - fail loudly
    with pytest.raises(FileNotFoundError):
        YamlWithIncludesSettingsSource(State, yaml_file=str(config_file))


def test_empty_include_list(fixtures_dir, tmp_path):
    """Empty include: list is handled correctly."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
include: []

config:
  git:
    source_ref: test/branch
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

    assert data["config"]["git"]["source_ref"] == "test/branch"


def test_include_with_no_config_section(fixtures_dir, tmp_path):
    """Include file with no config: section is handled."""
    partial_file = tmp_path / "partial.yaml"
    partial_file.write_text("""
# No config: section, just random data
random_key: random_value
""")

    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
include: {partial_file}

config:
  git:
    source_ref: test/branch
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

    # Should merge the random_key at top level
    assert "random_key" in data
    assert "config" in data


def test_absolute_include_path(fixtures_dir, tmp_path):
    """Include with absolute path works."""
    absolute_path = (fixtures_dir / "extra_commands.yaml").resolve()

    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
include: {absolute_path}

config:
  git:
    source_ref: test/branch
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

    assert "custom" in data["config"]["commands"]


def test_relative_include_from_nested_dir(fixtures_dir, tmp_path):
    """Include with ../ relative path resolves correctly."""
    # Create nested structure
    subdir = tmp_path / "nested" / "deep"
    subdir.mkdir(parents=True)

    config_file = subdir / "config.yaml"
    config_file.write_text("""
include: ../../extra.yaml

config:
  git:
    source_ref: nested/branch
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

    extra_file = tmp_path / "extra.yaml"
    extra_file.write_text("""
config:
  commands:
    custom:
      nested_test: "echo nested"
""")

    source = YamlWithIncludesSettingsSource(State, yaml_file=str(config_file))
    data = source()

    assert "custom" in data["config"]["commands"]
    assert data["config"]["commands"]["custom"]["nested_test"] == "echo nested"


def test_empty_yaml_file(fixtures_dir, tmp_path):
    """Empty YAML file is handled gracefully."""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")

    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
include: {empty_file}

config:
  git:
    source_ref: test/branch
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

    # Should still load main config
    assert data["config"]["git"]["source_ref"] == "test/branch"
