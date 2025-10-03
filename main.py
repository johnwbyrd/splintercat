#!/usr/bin/env python3
"""Splintercat - maintain stable git branches by applying and testing upstream patches."""

from src.core.config import Settings
from src.core.runner import Runner


def main():
    """Entry point."""
    settings = Settings()
    runner = Runner(settings)
    runner.run()


if __name__ == "__main__":
    main()
