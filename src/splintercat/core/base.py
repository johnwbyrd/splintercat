"""Base classes for configuration and state models.

This module contains the foundational classes used throughout
splintercat:
- Closeable Protocol for resource cleanup
- BaseCloseable for automatic cleanup cascade
- BaseConfig for configuration models
- BaseState for runtime state models

These are extracted into a separate module to avoid circular
dependencies between config.py and log.py.
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

# ============================================================
# CLOSEABLE PROTOCOL AND BASE CLASS
# ============================================================

@runtime_checkable
class Closeable(Protocol):
    """Protocol for objects that support close()."""

    def close(self) -> None:
        """Clean up resources."""
        ...


class BaseCloseable(BaseModel):
    """Base class providing automatic cleanup of Closeable children.

    Any Pydantic model inheriting from BaseCloseable:
    - Becomes a context manager (supports 'with' statement)
    - Automatically walks its fields on close()
    - Calls close() on any child that has the method
    - Continues closing remaining children even if some fail

    This creates a cleanup cascade:
    State.__exit__() → Config.close() → Logger.close() → Sink.close()
    """

    def close(self):
        """Close all closeable child objects.

        Walks through all model fields and calls close() on any
        Closeable objects. Continues even if some close() calls
        fail, logging errors to stderr.
        """
        for field_name in self.__class__.model_fields:
            child = getattr(self, field_name, None)
            if child is None:
                continue

            # Check if child implements Closeable protocol
            if isinstance(child, Closeable):
                try:
                    child.close()
                except Exception as e:
                    # Log error but continue closing other children
                    msg = f"Warning: Error closing {field_name}: {e}"
                    print(msg, file=sys.stderr)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: U100
        """Context manager exit - close all children.

        This is guaranteed to run by Python's context manager protocol,
        even when exceptions occur.
        """
        self.close()
        return False  # Don't suppress exceptions


# ============================================================
# BASE CLASSES (semantic markers for readers)
# ============================================================

class BaseConfig(BaseCloseable):
    """Base class for all configuration sections.

    Inherits from BaseCloseable to provide automatic cleanup.
    This serves as a semantic marker to indicate that a model
    represents configuration (loaded from YAML/env/CLI) rather
    than runtime state.
    """
    pass


class BaseState(BaseCloseable):
    """Base class for all runtime state sections.

    Inherits from BaseCloseable to provide automatic cleanup.
    This serves as a semantic marker to indicate that a model
    represents runtime state (mutated during workflow execution)
    rather than configuration.
    """
    pass


__all__ = ["Closeable", "BaseCloseable", "BaseConfig", "BaseState"]
