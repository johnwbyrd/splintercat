"""Conflict resolver using pydantic-AI agent with workspace tools."""

from pydantic_ai import Agent

from splintercat.tools import workspace_tools
from splintercat.tools.workspace import Workspace

# System prompt for the resolver agent
RESOLVER_PROMPT = """You are an expert conflict resolution assistant.

Your task is to resolve git merge conflicts using the workspace tools.

WORKFLOW:
1. Call list_files() to see available files
2. Read 'before' and 'after' to understand the context
3. Read 'ours' and 'theirs' to see both changes
4. Read 'base' (if available) to understand the original
5. Decide how to integrate both changes
6. Use cat_files() to compose resolution from before + content + after
7. Call submit_resolution() with your composed file

REQUIREMENTS:
- Resolution MUST start with 'before' content
- Resolution MUST end with 'after' content
- Resolution MUST integrate both changes when possible
- Prefer keeping both changes over discarding one
- If changes conflict, choose the most logical merge

Use the tools to work through the conflict systematically.
"""


def create_resolver_agent(model: str = "openai:gpt-4o") -> Agent:
    """Create a resolver agent with workspace tools.

    Args:
        model: Model identifier (e.g., 'openai:gpt-4o',
            'anthropic:claude-3-5-sonnet-20241022')

    Returns:
        Configured Agent ready to resolve conflicts
    """
    return Agent(
        model,
        deps_type=Workspace,
        tools=workspace_tools,
        system_prompt=RESOLVER_PROMPT,
    )


async def resolve_workspace(
    workspace: Workspace,
    model: str = "openai:gpt-4o",
    failure_context: str | None = None
) -> str:
    """Resolve a conflict using workspace and LLM agent.

    Args:
        workspace: Workspace containing conflict files
        model: Model identifier to use
        failure_context: Optional error context from previous
            attempt

    Returns:
        Resolved content (validated by submit_resolution)

    Raises:
        ValueError: If resolution is invalid or agent fails
    """
    agent = create_resolver_agent(model)

    # Build prompt with failure context if present
    prompt = "Resolve this merge conflict."
    if failure_context:
        prompt += (
            f"\n\nPREVIOUS ATTEMPT FAILED:\n{failure_context}\n\n"
            f"Please try again, taking the error into account."
        )

    # Run agent with workspace as dependencies
    result = await agent.run(prompt, deps=workspace)

    # The agent should call submit_resolution which validates
    # and returns the content
    return result.data
