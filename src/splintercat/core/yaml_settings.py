"""YAML configuration loading with include directive support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, YamlConfigSettingsSource


class YamlWithIncludesSettingsSource(YamlConfigSettingsSource):
    """YAML settings source with include: directive and --include CLI support.

    Automatically loads package defaults from defaults/default.yaml.
    Processes include: directives recursively within YAML files.
    Supports --include CLI args to load additional files.
    Deep merges all sources: defaults < config.yaml < CLI includes.
    """

    def __init__(
        self, settings_cls: type[BaseSettings], yaml_file=None
    ):
        """Initialize with CLI include processing.

        Args:
            settings_cls: The Settings class being initialized
            yaml_file: Optional override for user config file path
        """
        import sys

        # Parse --include from CLI before pydantic processes it
        includes = []
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "--include" and i + 1 < len(sys.argv):
                includes.append(sys.argv[i + 1])
                i += 1  # Skip the value
            i += 1

        # Get base yaml file and combine with includes
        base = yaml_file or settings_cls.model_config.get("yaml_file")
        if base and includes:
            yaml_file = (
                [base] if isinstance(base, str) else list(base)
            ) + includes
        elif includes:
            yaml_file = includes
        else:
            yaml_file = base

        super().__init__(settings_cls, yaml_file)

    def _read_files(self, files):
        """Load defaults, user config, and CLI includes with deep merge.

        Args:
            files: User config file path(s) from yaml_file setting

        Returns:
            Deep-merged dictionary of all loaded data
        """
        # Load package defaults
        default_file = (
            Path(__file__).parent.parent / "defaults" / "default.yaml"
        )
        result = {}

        if default_file.exists():
            result = self._load_file_recursive(default_file, set())

        # Load user files
        if files:
            if isinstance(files, (str, os.PathLike)):
                files = [files]
            for file in files:
                file_path = Path(file).expanduser()
                if file_path.is_file():
                    data = self._load_file_recursive(file_path, set())
                    result = self._deep_merge(result, data)

        return result

    def _load_file_recursive(
        self, filepath: Path, visited: set[Path]
    ) -> dict:
        """Load file and process include: directives recursively.

        Args:
            filepath: Path to YAML file to load
            visited: Set of already-visited files for cycle detection

        Returns:
            Dictionary with all includes resolved and merged

        Raises:
            ValueError: If circular include detected
        """
        if filepath in visited:
            raise ValueError(f"Circular include: {filepath}")
        visited.add(filepath)

        with open(filepath) as f:
            data = yaml.safe_load(f) or {}

        # Process include: directive
        if "include" in data:
            includes = data.pop("include")
            if isinstance(includes, str):
                includes = [includes]

            for inc in includes:
                inc_path = self._resolve_path(inc, filepath)
                inc_data = self._load_file_recursive(
                    inc_path, visited.copy()
                )
                data = self._deep_merge(inc_data, data)

        return data

    def _resolve_path(
        self, include_path: str, relative_to: Path
    ) -> Path:
        """Resolve include path relative to including file.

        Args:
            include_path: Path from include: directive
            relative_to: Path of file containing the include

        Returns:
            Resolved absolute path
        """
        path = Path(include_path)
        if path.is_absolute():
            return path
        return (relative_to.parent / path).resolve()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge override into base (override wins).

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            New dictionary with deep merge applied
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
