#!/usr/bin/env python3
"""Splintercat - Model-assisted git merge conflict resolution."""

from src.core.config import CliApp, CliSettings


def main():
    """Main entry point."""
    CliApp.run(CliSettings)


if __name__ == "__main__":
    main()
