#!/usr/bin/env python3
"""Splintercat - LLM-assisted git merge conflict resolution."""

import asyncio

from pydantic_settings import CliApp, CliSubCommand, get_subcommand

from src.command.merge import MergeCommand
from src.command.reset import ResetCommand
from src.core.config import State


class CliState(State):
    """State with CLI subcommand support.

    This extends State to add CLI subcommand dispatch.
    When run via CliApp.run(CliState), pydantic-settings will:
    1. Parse CLI arguments
    2. Load config from YAML/env
    3. Instantiate CliState
    4. Call cli_cmd() method
    5. Dispatch to the active subcommand
    """

    merge: CliSubCommand[MergeCommand]
    reset: CliSubCommand[ResetCommand]

    def cli_cmd(self):
        """Dispatch to active subcommand.

        This is called by CliApp.run() after parsing arguments.
        It extracts the active subcommand and runs its workflow.
        """
        subcommand = get_subcommand(self)

        # self IS State with all config loaded
        # Pass self to the command's run_workflow method
        exit_code = asyncio.run(subcommand.run_workflow(self))
        raise SystemExit(exit_code)


if __name__ == "__main__":
    CliApp.run(CliState)
