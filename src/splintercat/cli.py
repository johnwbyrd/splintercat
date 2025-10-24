#!/usr/bin/env python3
"""Splintercat CLI - LLM-assisted git merge conflict resolution."""

import asyncio

from pydantic_settings import CliApp, CliSubCommand, get_subcommand

from splintercat.command.merge import MergeCommand
from splintercat.command.reset import ResetCommand
from splintercat.core.config import State


class CliState(State):
    """LLM-assisted git merge conflict resolution with
    incremental merging.

    Splintercat uses git-imerge to break large merges into
    smaller pieces, resolves conflicts with LLM assistance,
    validates with build/test, and implements smart recovery
    strategies when conflicts arise.

    Configuration sources (in priority order):
    1. Command-line arguments (--config.git.source_ref value)
    2. config.yaml file in current directory
    3. .env file for secrets
    4. Environment variables
       (SPLINTERCAT__CONFIG__GIT__SOURCE_REF=value)

    The [JSON] options allow setting multiple values at once:
      --config.git '{"source_ref": "main", "target_branch":
      "stable"}'
    """

    merge: CliSubCommand[MergeCommand]
    reset: CliSubCommand[ResetCommand]

    def cli_cmd(self):
        """Dispatch to active subcommand, or show help if none
        provided."""
        subcommand = get_subcommand(self, is_required=False)

        if subcommand is None:
            # No subcommand provided, show help
            import sys
            CliApp.run(CliState, cli_args=['--help'])
            sys.exit(1)

        # Setup logging with file output for this command
        from pathlib import Path

        from splintercat.core.log import logger

        # Get command name (merge, reset, etc.)
        command_name = (
            subcommand.__class__.__name__.replace('Command', '').lower()
        )

        # Extract project name from target_workdir for log organization
        project_name = Path(self.config.git.target_workdir).name

        logger.setup(
            self.config.log_level,
            agent_log_dir=Path(self.config.agent_log_dir),
            command=command_name,
            project_name=project_name
        )

        # self IS State with all config loaded
        # Pass self to the command's run_workflow method
        exit_code = asyncio.run(subcommand.run_workflow(self))
        raise SystemExit(exit_code)


def main():
    """Main entry point for CLI."""
    CliApp.run(CliState)


if __name__ == "__main__":
    main()
