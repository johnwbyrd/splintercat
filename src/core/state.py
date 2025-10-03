"""State and Result models for strategy decision-making."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.patchset import PatchSet


class Result(BaseModel):
    """Result of one attempt to apply and test a patchset."""

    patch_ids: list[str]
    success: bool
    applied: bool  # True if patches applied (even if tests failed)
    failed_patch_id: str | None = None  # ID of patch that failed to apply
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_apply: float = 0.0
    duration_test: float = 0.0
    apply_output: str = ""
    test_output: str = ""
    error_message: str | None = None

    model_config = {"arbitrary_types_allowed": True}


class State(BaseModel):
    """Complete state for strategy decision-making.

    Contains original patchset and history of all attempts.
    Strategy uses this to decide what to try next.
    """

    original_patchset: PatchSet
    results: list[Result] = Field(default_factory=list)
    done: bool = False
    strategy_data: dict = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    def record_result(
        self,
        patchset: PatchSet,
        success: bool,
        applied: bool,
        failed_patch_id: str | None = None,
        duration_apply: float = 0.0,
        duration_test: float = 0.0,
        apply_output: str = "",
        test_output: str = "",
        error_message: str | None = None,
    ):
        """Record an attempt result.

        Args:
            patchset: PatchSet that was attempted
            success: Whether apply + test succeeded
            applied: Whether patches applied (even if tests failed)
            failed_patch_id: ID of patch that failed to apply (if any)
            duration_apply: Seconds spent applying patches
            duration_test: Seconds spent testing
            apply_output: Output from git am
            test_output: Output from test command
            error_message: Error message if failed
        """
        patch_ids = [patch.id for patch in patchset]

        result = Result(
            patch_ids=patch_ids,
            success=success,
            applied=applied,
            failed_patch_id=failed_patch_id,
            duration_apply=duration_apply,
            duration_test=duration_test,
            apply_output=apply_output,
            test_output=test_output,
            error_message=error_message,
        )

        self.results.append(result)

    def get_strategy_data(self, key: str, default=None):
        """Get strategy-specific data.

        Args:
            key: Key to retrieve
            default: Default value if key doesn't exist

        Returns:
            Value for key, or default if not found
        """
        return self.strategy_data.get(key, default)

    def set_strategy_data(self, key: str, value):
        """Set strategy-specific data.

        Args:
            key: Key to set
            value: Value to store
        """
        self.strategy_data[key] = value
