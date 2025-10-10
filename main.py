#!/usr/bin/env python3
"""Splintercat - Model-assisted git merge conflict resolution."""

import asyncio
import sys

from src.app import SplintercatApp
from src.core.config import Settings


def main():
    """Main entry point."""
    settings = Settings()
    app = SplintercatApp(settings)
    sys.exit(asyncio.run(app.run()))


if __name__ == "__main__":
    main()
