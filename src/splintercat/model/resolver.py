"""Conflict resolver using pydantic-AI agent with workspace tools."""

from contextlib import contextmanager

from pydantic_ai import Agent, providers

from splintercat.core.config import LLMConfig
from splintercat.core.log import logger
from splintercat.tools import workspace_tools
from splintercat.tools.workspace import Workspace


@contextmanager
def inject_provider_params(llm_config: LLMConfig):
    """Context manager to inject parameters into provider creation.

    Temporarily patches pydantic-AI's infer_provider to pass
    custom parameters to provider constructors. Restores original
    behavior on exit.

    Args:
        llm_config: LLM configuration with api_key, base_url, etc.

    Yields:
        None
    """
    # Build kwargs from config
    kwargs = {}
    if llm_config.api_key:
        kwargs['api_key'] = llm_config.api_key
    if llm_config.base_url:
        kwargs['base_url'] = llm_config.base_url

    if not kwargs:
        # No patching needed
        yield
        return

    # Save original
    original_infer_provider = providers.infer_provider

    def patched_infer_provider(provider_name: str):
        """Infer provider and inject parameters."""
        provider_class = providers.infer_provider_class(provider_name)
        return provider_class(**kwargs)

    try:
        providers.infer_provider = patched_infer_provider
        yield
    finally:
        providers.infer_provider = original_infer_provider


class WorkspaceResolver:
    """Resolves workspace conflicts using LLM agent with extensive
    debugging.
    """

    def __init__(self, llm_config: LLMConfig, workspace_config=None):
        """Initialize resolver with LLM configuration.

        Args:
            llm_config: LLM configuration (model, api_key,
                base_url, etc.)
            workspace_config: Optional workspace config for
                prompts and agent settings
        """
        self.llm_config = llm_config
        self.system_prompt = self._extract_system_prompt(workspace_config)
        self.retries = self._extract_retries(workspace_config)

    def _extract_system_prompt(self, workspace_config) -> str | None:
        """Extract system prompt from workspace config.

        Args:
            workspace_config: Workspace configuration object

        Returns:
            System prompt string or None for default
        """
        if workspace_config and hasattr(workspace_config, 'prompts'):
            prompts = workspace_config.prompts
            if 'resolver' in prompts and 'system' in prompts['resolver']:
                return prompts['resolver']['system']
        return None

    def _extract_retries(self, workspace_config) -> int:
        """Extract retry count from workspace config.

        Args:
            workspace_config: Workspace configuration object

        Returns:
            Retry count (default 5)
        """
        if workspace_config and hasattr(workspace_config, 'agents'):
            agents = workspace_config.agents
            if 'resolver' in agents and 'retries' in agents['resolver']:
                return agents['resolver']['retries']
        return 5  # Default

    def _create_agent(self) -> Agent:
        """Create resolver agent with current configuration.

        Returns:
            Configured Agent ready to resolve conflicts
        """
        system_prompt = (
            self.system_prompt or
            "You are a git merge conflict resolver."
        )

        with inject_provider_params(self.llm_config):
            return Agent(
                self.llm_config.model,
                deps_type=Workspace,
                tools=workspace_tools,
                system_prompt=system_prompt,
                retries=self.retries,
            )

    def _build_prompt(
        self, workspace: Workspace, failure_context: str | None
    ) -> str:
        """Build resolution prompt with optional failure context.

        Args:
            workspace: Workspace containing conflict files
            failure_context: Optional error context from previous
                attempt

        Returns:
            Formatted prompt string
        """
        files_str = ', '.join(workspace.conflict_files)
        prompt = f"Resolve conflicts in these files: {files_str}"
        if failure_context:
            prompt += (
                f"\n\nPREVIOUS ATTEMPT FAILED:\n{failure_context}\n\n"
                f"Please try again, taking the error into account."
            )
        return prompt

    def _log_pre_call_debug_info(self, workspace: Workspace, prompt: str):
        """Log extensive debug info before calling LLM API.

        This helps diagnose provider connection issues, configuration
        problems, and prompt construction errors.

        Args:
            workspace: Workspace being resolved
            prompt: Prompt being sent to LLM
        """
        logger.debug(
            f"Creating resolver agent with model: "
            f"{self.llm_config.model}"
        )
        logger.debug(
            f"API key provided: {self.llm_config.api_key is not None}"
        )
        logger.debug(f"Base URL: {self.llm_config.base_url}")
        if self.llm_config.api_key:
            logger.debug(f"API key prefix: {self.llm_config.api_key[:10]}...")
        logger.debug(f"Retries: {self.retries}")

        logger.debug(f"Workspace workdir: {workspace.workdir}")
        logger.debug(f"Conflict files: {workspace.conflict_files}")
        logger.debug(f"Prompt: {prompt}")
        logger.debug(f"Prompt length: {len(prompt)} chars")

        if self.system_prompt:
            logger.debug(
                f"Agent system prompt length: {len(self.system_prompt)}"
            )
        logger.debug(f"Workspace object: {workspace}")

    def _log_agent_debug_info(self, agent: Agent):
        """Log agent configuration details.

        Args:
            agent: Agent to inspect
        """
        logger.debug(f"Agent created: {agent}")
        logger.debug(f"Agent model: {agent.model}")
        logger.debug(f"Agent model name: {agent.model.model_name}")

    def _log_exception_debug_info(self, e: Exception):
        """Log extensive exception details for debugging LLM failures.

        This is critical for diagnosing:
        - API connection failures
        - Malformed JSON responses
        - Unexpected model behavior
        - Provider-specific issues

        Args:
            e: Exception that occurred during resolution
        """
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

    def _log_result_debug_info(self, result):
        """Log extensive result details for debugging LLM responses.

        This helps understand:
        - What the LLM actually returned
        - Whether expected tools were called
        - Message flow and structure

        Args:
            result: Result from agent.run()
        """
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

    async def resolve(
        self, workspace: Workspace, failure_context: str | None = None
    ) -> str:
        """Resolve workspace conflicts using LLM agent.

        Args:
            workspace: Workspace containing conflict files
            failure_context: Optional error context from previous
                attempt

        Returns:
            Resolved content (validated by submit_resolution)

        Raises:
            ValueError: If resolution is invalid or agent fails
        """
        # Build prompt
        prompt = self._build_prompt(workspace, failure_context)

        # Log pre-call debug info
        self._log_pre_call_debug_info(workspace, prompt)

        # Create agent
        agent = self._create_agent()
        self._log_agent_debug_info(agent)

        # Run agent with workspace as dependencies
        logger.debug("Calling LLM API...")
        try:
            result = await agent.run(prompt, deps=workspace)
            logger.debug("LLM API call completed")
        except Exception as e:
            self._log_exception_debug_info(e)
            raise

        # Log result debug info
        self._log_result_debug_info(result)

        # The agent should call submit_resolution which validates
        # and returns the content
        return result.output


async def resolve_workspace(
    workspace: Workspace,
    llm_config: LLMConfig,
    failure_context: str | None = None
) -> str:
    """Resolve workspace conflicts using LLM agent.

    Args:
        workspace: Workspace containing conflict files
        llm_config: LLM configuration (model, api_key, base_url, etc.)
        failure_context: Optional error context from previous attempt

    Returns:
        Resolved content (validated by submit_resolution)

    Raises:
        ValueError: If resolution is invalid or agent fails
    """
    resolver = WorkspaceResolver(llm_config, workspace.config)
    return await resolver.resolve(workspace, failure_context)
