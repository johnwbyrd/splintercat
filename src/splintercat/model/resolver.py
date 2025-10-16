"""Conflict resolver using pydantic-AI agent with workspace tools."""

from contextlib import contextmanager

from pydantic_ai import Agent, providers

from splintercat.core.log import logger
from splintercat.tools import workspace_tools
from splintercat.tools.workspace import Workspace


@contextmanager
def inject_provider_api_key(api_key: str | None):
    """Context manager to inject API key into provider creation.

    Temporarily patches pydantic-AI's infer_provider to pass api_key
    to provider constructors. Restores original behavior on exit.

    Args:
        api_key: API key to inject, or None to use default behavior

    Yields:
        None
    """
    if not api_key:
        # No patching needed
        yield
        return

    # Save original
    original_infer_provider = providers.infer_provider

    def patched_infer_provider(provider_name: str):
        """Infer provider and inject api_key."""
        provider_class = providers.infer_provider_class(provider_name)
        return provider_class(api_key=api_key)

    try:
        providers.infer_provider = patched_infer_provider
        yield
    finally:
        providers.infer_provider = original_infer_provider


def create_resolver_agent(
    model: str = "openai:gpt-4o",
    api_key: str | None = None,
    system_prompt: str | None = None
) -> Agent:
    """Create a resolver agent with workspace tools.

    Args:
        model: Model identifier (e.g., 'openai:gpt-4o',
            'anthropic:claude-3-5-sonnet-20241022')
        api_key: Optional API key (if None, providers use env vars)
        system_prompt: System prompt to use (if None, uses default)

    Returns:
        Configured Agent ready to resolve conflicts
    """
    # Default prompt if none provided
    if not system_prompt:
        system_prompt = "You are a git merge conflict resolver."

    with inject_provider_api_key(api_key):
        return Agent(
            model,
            deps_type=Workspace,
            tools=workspace_tools,
            system_prompt=system_prompt,
        )


async def resolve_workspace(
    workspace: Workspace,
    model: str = "openai:gpt-4o",
    api_key: str | None = None,
    failure_context: str | None = None
) -> str:
    """Resolve a conflict using workspace and LLM agent.

    Args:
        workspace: Workspace containing conflict files
        model: Model identifier to use
        api_key: Optional API key (if None, providers use env vars)
        failure_context: Optional error context from previous
            attempt

    Returns:
        Resolved content (validated by submit_resolution)

    Raises:
        ValueError: If resolution is invalid or agent fails
    """
    # Get system prompt from config
    system_prompt = None
    if workspace.config and hasattr(workspace.config, 'prompts'):
        prompts = workspace.config.prompts
        if 'resolver' in prompts and 'system' in prompts['resolver']:
            system_prompt = prompts['resolver']['system']

    logger.debug(f"Creating resolver agent with model: {model}")
    logger.debug(f"API key provided: {api_key is not None}")
    if api_key:
        logger.debug(f"API key prefix: {api_key[:10]}...")

    agent = create_resolver_agent(model, api_key, system_prompt)
    logger.debug(f"Agent created: {agent}")
    logger.debug(f"Agent model: {agent.model}")
    logger.debug(f"Agent model name: {agent.model.model_name}")

    # Build prompt with failure context if present
    files_str = ', '.join(workspace.conflict_files)
    prompt = f"Resolve conflicts in these files: {files_str}"
    if failure_context:
        prompt += (
            f"\n\nPREVIOUS ATTEMPT FAILED:\n{failure_context}\n\n"
            f"Please try again, taking the error into account."
        )

    # Log workspace info for debugging
    logger.debug(f"Workspace workdir: {workspace.workdir}")
    logger.debug(f"Conflict files: {workspace.conflict_files}")
    logger.debug(f"Prompt: {prompt}")
    logger.debug(f"Prompt length: {len(prompt)} chars")

    # Run agent with workspace as dependencies
    logger.debug("Calling LLM API...")
    if system_prompt:
        logger.debug(f"Agent system prompt length: {len(system_prompt)}")
    logger.debug(f"Workspace object: {workspace}")

    try:
        result = await agent.run(prompt, deps=workspace)
        logger.debug("LLM API call completed")
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception __cause__: {e.__cause__}")

        # For JSONDecodeError, show the problematic document
        if hasattr(e, 'doc'):
            logger.error(
                f"JSONDecodeError at line {e.lineno}, "
                f"col {e.colno}, pos {e.pos}"
            )
            # Show context around the error position
            doc = e.doc
            start = max(0, e.pos - 200)
            end = min(len(doc), e.pos + 200)
            context = doc[start:end]
            logger.error(f"Context around error:\n{context}")
            logger.error(f"Full doc length: {len(doc)} chars")
            # Save full response for debugging
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode='w', delete=False, suffix='.json'
            ) as f:
                f.write(doc)
                logger.error(f"Full response saved to: {f.name}")

        # Check for UnexpectedModelBehavior attributes
        if hasattr(e, 'message'):
            logger.error(f"Exception message: {e.message}")
        if hasattr(e, 'body'):
            logger.error(f"Exception body: {e.body}")

        # Check all exception attributes
        logger.error(f"Exception __dict__: {e.__dict__}")
        raise

    # The agent should call submit_resolution which validates
    # and returns the content
    logger.debug(f"Resolution result type: {type(result)}")

    if hasattr(result, 'output'):
        try:
            # Limit to avoid huge output
            output_repr = repr(result.output)[:200]
            logger.debug(f"Resolution output (truncated): {output_repr}")
            logger.debug(f"Resolution output type: {type(result.output)}")
        except Exception as e:
            logger.debug(f"Failed to access result.output: {e}")

    if hasattr(result, 'all_messages'):
        try:
            messages = result.all_messages()
            logger.debug(f"Result has {len(messages)} messages")

            # Check if submit_resolution was called
            for msg in reversed(messages):
                logger.debug(f"Message type: {type(msg).__name__}")
                if hasattr(msg, 'parts'):
                    for part in msg.parts:
                        logger.debug(f"  Part type: {type(part).__name__}")
                        if hasattr(part, 'tool_name'):
                            logger.debug(f"    Tool: {part.tool_name}")
                        if hasattr(part, 'content'):
                            try:
                                content_len = len(str(part.content))
                                logger.debug(
                                    f"    Content length: {content_len}"
                                )
                            except Exception as e:
                                logger.debug(
                                    f"    Failed to get content "
                                    f"length: {e}"
                                )
        except Exception as e:
            logger.debug(f"Failed to process messages: {e}")

    # Return result.output
    return result.output
