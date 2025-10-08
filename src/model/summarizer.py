"""Build log summarizer model."""

from pathlib import Path


class BuildFailureSummary:
    """Structured summary of a build failure."""

    def __init__(
        self,
        error_type: str,
        location: str,
        root_cause: str,
        excerpt: str,
    ):
        """Initialize build failure summary.

        Args:
            error_type: Type of error (compile_error, link_error, test_failure, timeout)
            location: File:line or test name where error occurred
            root_cause: One-sentence description of root cause
            excerpt: Relevant error message excerpt
        """
        self.error_type = error_type
        self.location = location
        self.root_cause = root_cause
        self.excerpt = excerpt


class Summarizer:
    """LLM model for summarizing build/test logs.

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

    def summarize_failure(self, log_file: Path) -> BuildFailureSummary:
        """Summarize a build/test failure from log file.

        Args:
            log_file: Path to build/test log file

        Returns:
            Structured summary of the failure
        """
        pass
