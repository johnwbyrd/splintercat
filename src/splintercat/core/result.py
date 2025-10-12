"""Result types for check execution."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class CheckResult(BaseModel):
    """Result of a check execution."""

    check_name: str
    success: bool
    log_file: Path
    returncode: int
    timestamp: datetime
