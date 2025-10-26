"""YAML configuration loading with include directive support."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from platformdirs import user_config_dir
from pydantic_settings import BaseSettings, YamlConfigSettingsSource

# Bootstrap logger - created lazily to avoid circular import
_bootstrap_logger = None


def _get_bootstrap_logger():
    """Get or create bootstrap logger for config loading.

    Created lazily to avoid circular import at module load time.
    """
    global _bootstrap_logger
    if _bootstrap_logger is None:
        from splintercat.core.log import Logger
        _bootstrap_logger = Logger()
        _bootstrap_logger.setup(log_root=Path.home(), merge_name="bootstrap")
    return _bootstrap_logger


def _cleanup_bootstrap_logger():
    """Clean up bootstrap logger after config loads.

    Called after Config initializes the global logger singleton.
    """
    global _bootstrap_logger
    if _bootstrap_logger:
        _bootstrap_logger.close()
        _bootstrap_logger = None


class YamlWithIncludesSettingsSource(YamlConfigSettingsSource):
    """YAML settings source with include: directive and --include
    CLI support.

    Automatically loads package defaults from
    defaults/default.yaml.
    Checks for user and project config files in
    platform-specific locations.
    Processes include: directives recursively within YAML files.
    Supports --include CLI args to load additional files.
    Deep merges all sources:
        defaults < user config < project config < CLI includes.
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
        """Load defaults, user config, project config, and CLI includes.

        Loads configuration from multiple locations in priority order:
        1. Package defaults (defaults/default.yaml) - always loaded
        2. User config (platform-specific location) - if exists
        3. Project config (./splintercat.yaml) - if exists
        4. CLI includes (--include files) - if provided

        Args:
            files: CLI include file path(s) from --include arguments

        Returns:
            Deep-merged dictionary of all loaded data
        """
        result = {}

        # Build list of files to check in priority order
        files_to_load = []

        # 1. Package defaults (always first)
        default_file = (
            Path(__file__).parent.parent / "defaults" / "default.yaml"
        )
        files_to_load.append(default_file)

        # 2. User config (platform-specific location)
        user_config = (
            Path(user_config_dir("splintercat", appauthor=False))
            / "splintercat.yaml"
        )
        files_to_load.append(user_config)

        # 3. Project config (current directory)
        project_config = Path("splintercat.yaml")
        files_to_load.append(project_config)

        # 4. CLI includes (highest priority)
        if files:
            if isinstance(files, (str, os.PathLike)):
                files = [files]
            files_to_load.extend(Path(f).expanduser() for f in files)

        # Load and merge all files that exist
        for file_path in files_to_load:
            if file_path.is_file():
                with _get_bootstrap_logger().span(
                    "Configuration loading",
                    file=str(file_path),
                ):
                    data = self._load_file_recursive(file_path, set())
                    result = self._deep_merge(result, data)
            else:
                _get_bootstrap_logger().debug(
                    "Configuration file not found (skipping)",
                    file=str(file_path),
                )

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
                with _get_bootstrap_logger().span(
                    f"Including {inc_path.name}",
                    included_from=str(filepath),
                    include_file=str(inc_path),
                ):
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
