"""Strategic planner model."""


class StrategyDecision:
    """Decision about merge strategy."""

    def __init__(self, strategy: str, batch_size: int | None, reasoning: str):
        """Initialize strategy decision.

        Args:
            strategy: Strategy name (optimistic, batch, per_conflict)
            batch_size: Batch size if strategy is 'batch'
            reasoning: Explanation of the decision
        """
        self.strategy = strategy
        self.batch_size = batch_size
        self.reasoning = reasoning


class RecoveryDecision:
    """Decision about recovery approach after build failure."""

    def __init__(
        self,
        decision: str,
        conflicts_to_retry: list[tuple[int, int]] | None,
        new_strategy: str | None,
        reasoning: str,
    ):
        """Initialize recovery decision.

        Args:
            decision: Recovery approach (retry-all,
                retry-specific, bisect, switch-strategy, abort)
            conflicts_to_retry: Specific conflicts to retry if
                decision is retry-specific
            new_strategy: New strategy name if decision is
                switch-strategy
            reasoning: Explanation of the decision
        """
        self.decision = decision
        self.conflicts_to_retry = conflicts_to_retry
        self.new_strategy = new_strategy
        self.reasoning = reasoning


class Planner:
    """LLM model for strategic planning and decision making.

    Uses a smart/expensive model to make all strategic and
    tactical decisions.
    """

    def __init__(self, model: str, api_key: str, base_url: str):
        """Initialize planner model.

        Args:
            model: Model name (e.g., anthropic/claude-sonnet-4)
            api_key: API key for the model provider
            base_url: Base URL for the model API
        """
        pass

    def choose_initial_strategy(
        self,
        source_ref: str,
        target_branch: str,
        num_source_commits: int,
        num_target_commits: int,
        available_strategies: list[str],
        default_batch_size: int,
    ) -> StrategyDecision:
        """Choose initial merge strategy.

        Args:
            source_ref: Source git ref being merged
            target_branch: Target branch being merged into
            num_source_commits: Number of commits in source
            num_target_commits: Number of commits in target
            available_strategies: List of available strategy names
            default_batch_size: Default batch size for batch strategy

        Returns:
            Strategy decision with reasoning
        """
        pass

    def plan_recovery(
        self,
        current_strategy: str,
        conflicts_resolved_count: int,
        failure_summary: str,
        conflicts_in_attempt: list[tuple[int, int]],
        attempt_history: list[dict],
        max_retries: int,
        current_attempt: int,
    ) -> RecoveryDecision:
        """Plan recovery approach after build failure.

        Args:
            current_strategy: Current merge strategy
            conflicts_resolved_count: Number of conflicts
                resolved in this attempt
            failure_summary: Summary of build failure
            conflicts_in_attempt: List of conflict pairs in this
                attempt
            attempt_history: History of previous attempts
            max_retries: Maximum retry limit
            current_attempt: Current attempt number

        Returns:
            Recovery decision with reasoning
        """
        pass
