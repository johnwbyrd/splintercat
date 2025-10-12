"""Tests for deep merge and priority behavior."""

from pathlib import Path

import pytest

from splintercat.core.config import State
from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


def test_deep_merge_preserves_non_overlapping(fixtures_dir):
    """Deep merge preserves values that don't conflict."""
    # minimal.yaml has full config
    # override_strategy.yaml only has strategy and one git command
    # Result should have both

    from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource

    source = YamlWithIncludesSettingsSource(State)

    # Manually test deep merge
    base = {
        "config": {
            "git": {"source_ref": "base", "target_workdir": "/tmp"},
            "strategy": {"max_retries": 3, "available": ["optimistic"]},
        }
    }

    override = {
        "config": {
            "git": {"source_ref": "override"},  # Override this
            "strategy": {"max_retries": 99},  # Override this
        }
    }

    result = source._deep_merge(base, override)

    # Overridden values
    assert result["config"]["git"]["source_ref"] == "override"
    assert result["config"]["strategy"]["max_retries"] == 99

    # Preserved values
    assert result["config"]["git"]["target_workdir"] == "/tmp"
    assert result["config"]["strategy"]["available"] == ["optimistic"]


def test_deep_merge_adds_new_keys(fixtures_dir):
    """Deep merge adds new keys from override."""
    from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource

    source = YamlWithIncludesSettingsSource(State)

    base = {
        "config": {
            "commands": {
                "git": {"fetch": "git fetch"}
            }
        }
    }

    override = {
        "config": {
            "commands": {
                "custom": {"test": "echo test"}  # New category
            }
        }
    }

    result = source._deep_merge(base, override)

    # Both should exist
    assert "git" in result["config"]["commands"]
    assert "custom" in result["config"]["commands"]


def test_deep_merge_nested_dicts(fixtures_dir):
    """Deep merge works at arbitrary nesting levels."""
    from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource

    source = YamlWithIncludesSettingsSource(State)

    base = {
        "a": {
            "b": {
                "c": {
                    "d": "base_value",
                    "e": "preserved"
                }
            }
        }
    }

    override = {
        "a": {
            "b": {
                "c": {
                    "d": "override_value"
                }
            }
        }
    }

    result = source._deep_merge(base, override)

    assert result["a"]["b"]["c"]["d"] == "override_value"
    assert result["a"]["b"]["c"]["e"] == "preserved"


def test_merge_order_matters(fixtures_dir, tmp_path):
    """Files merged later override files merged earlier."""
    # Create three files with conflicting values
    file1 = tmp_path / "file1.yaml"
    file1.write_text("""
config:
  strategy:
    max_retries: 1
""")

    file2 = tmp_path / "file2.yaml"
    file2.write_text("""
config:
  strategy:
    max_retries: 2
""")

    file3 = tmp_path / "file3.yaml"
    file3.write_text("""
config:
  strategy:
    max_retries: 3
""")

    from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource

    # Load in order: file1, file2, file3
    source = YamlWithIncludesSettingsSource(
        State,
        yaml_file=[str(file1), str(file2), str(file3)]
    )
    data = source()

    # Last file wins
    assert data["config"]["strategy"]["max_retries"] == 3


def test_defaults_lowest_priority(fixtures_dir):
    """Package defaults have lowest priority."""
    # User config should override defaults

    source = YamlWithIncludesSettingsSource(
        State,
        yaml_file=str(fixtures_dir / "override_strategy.yaml")
    )
    data = source()

    # User override wins
    assert data["config"]["strategy"]["max_retries"] == 99

    # But defaults still present for non-overridden values
    assert "available" in data["config"]["strategy"]
    expected = ["optimistic", "batch", "per_conflict"]
    assert data["config"]["strategy"]["available"] == expected


def test_list_replacement_not_merge(fixtures_dir):
    """Lists are replaced, not merged."""
    from splintercat.core.yaml_settings import YamlWithIncludesSettingsSource

    source = YamlWithIncludesSettingsSource(State)

    base = {
        "config": {
            "strategy": {
                "available": ["optimistic", "batch"]
            }
        }
    }

    override = {
        "config": {
            "strategy": {
                "available": ["per_conflict"]
            }
        }
    }

    result = source._deep_merge(base, override)

    # List is replaced, not merged
    assert result["config"]["strategy"]["available"] == ["per_conflict"]
