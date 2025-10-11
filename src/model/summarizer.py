"""Check log summarizer model."""

from pathlib import Path


class CheckFailureSummary:
    """Structured summary of a check failure."""

    def __init__(
        self,
        check_name: str,
        error_type: str,
        location: str,
        root_cause: str,
        excerpt: str,
    ):
        """Initialize check failure summary.

        Args:
            check_name: Name of check that failed
            error_type: Type of error (compile_error, link_error, test_failure, timeout)
            location: File:line or test name where error occurred
            root_cause: One-sentence description of root cause
            excerpt: Relevant error message excerpt
        """
        self.check_name = check_name
        self.error_type = error_type
        self.location = location
        self.root_cause = root_cause
        self.excerpt = excerpt


class Summarizer:
    """LLM model for summarizing check logs.

    Uses a cheap/fast model to extract actionable error information from verbose logs.
    """

    def __init__(self, model: str, api_key: str, base_url: str):
        """Initialize summarizer model.

        Args:
            model: Model name (e.g., openai/gpt-4o-mini)
            api_key: API key for the model provider
            base_url: Base URL for the model API
        """
        pass

    def summarize_failure(self, log_file: Path) -> CheckFailureSummary:
        """Summarize a check failure from log file.

        Args:
            log_file: Path to check log file

        Returns:
            Structured summary of the failure
        """
        pass
