"""LangGraph state machine definition and routing logic."""


def create_workflow():
    """Create and configure the LangGraph workflow.

    Defines nodes, edges, and routing logic for the merge workflow state machine.

    Routing logic:
    - BuildTest result: success -> Finalize, failure -> SummarizeFailure
    - PlanRecovery decision routing:
      - retry (retry-all or retry-specific) -> ResolveConflicts with failure context
      - bisect -> BuildTest with resolution subset
      - switch-strategy -> PlanStrategy
      - abort -> END

    Returns:
        Configured LangGraph workflow
    """
    pass
