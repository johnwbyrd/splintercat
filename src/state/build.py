"""Build and test result models."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class BuildResult(BaseModel):
    """Result of a build/test execution."""

    success: bool
    log_file: Path
    returncode: int
    timestamp: datetime
