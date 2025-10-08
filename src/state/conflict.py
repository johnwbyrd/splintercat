"""Conflict tracking and resolution models."""

from datetime import datetime

from pydantic import BaseModel


class ConflictInfo(BaseModel):
    """Information about a conflict between two commits."""

    i1: int
    i2: int
    files: list[str]


class ConflictResolution(BaseModel):
    """A resolved conflict with metadata."""

    conflict_pair: tuple[int, int]
    files: list[str]
    resolution: str
    attempt_number: int
    timestamp: datetime
