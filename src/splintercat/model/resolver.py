"""Conflict resolver using pydantic-AI agent with workspace tools."""

import traceback
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
        # Log with proper exception info so logfire captures it at
        # ERROR level
        logger.error("LLM API call failed", _exc_info=e)

        # Log formatted traceback for easy reading
        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
        logger.error("Exception traceback:\n" + ''.join(tb_lines))

        # Log exception attributes for structured data
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

        # Walk the exception cause chain to find underlying errors
        cause = e.__cause__
        depth = 1
        while cause:
            logger.error(
                f"Exception cause chain (depth {depth}): {cause}",
                _exc_info=cause
            )
            logger.error(f"Cause type: {type(cause)}")
            logger.error(f"Cause __dict__: {cause.__dict__}")
            cause = cause.__cause__
            depth += 1

        # Check exception context (different from cause)
        if e.__context__ is not None and e.__context__ is not e.__cause__:
            logger.error(
                f"Exception context: {e.__context__}",
                _exc_info=e.__context__
            )

    def _log_message_history(self, messages: list):
        """Log complete LLM conversation with full message part details.

        Uses dataclass fields from pydantic-ai message parts to provide
        comprehensive logging with correlation IDs, timestamps, and
        metadata.
        """
        logger.info(
            f"LLM conversation: {len(messages)} messages",
            message_count=len(messages)
        )

        # Build correlation map: tool_call_id -> tool_name for tracking
        tool_calls = {}

        for i, msg in enumerate(messages, 1):
            role = getattr(msg, 'role', 'unknown')
            logger.info(f"Message {i} [{role}]", message_index=i, role=role)

            if hasattr(msg, 'parts'):
                for _part_idx, part in enumerate(msg.parts):
                    part_type = type(part).__name__

                    if 'UserPrompt' in part_type:
                        content = getattr(part, 'content', '')
                        logger.info(
                            f"  User: {content}",
                            part_type="user_prompt",
                            content_length=len(str(content)),
                        )

                    elif 'Text' in part_type:
                        content = getattr(part, 'content', '')
                        logger.info(
                            f"  Model: {content}",
                            part_type="text",
                            content_length=len(str(content)),
                        )

                    elif 'ToolCall' in part_type:
                        # Use dataclass fields for structured logging
                        tool_name = part.tool_name
                        tool_call_id = part.tool_call_id

                        # Get args as dict for better logging
                        try:
                            args = part.args_as_dict()
                        except Exception:
                            args = part.args

                        # Store for correlation
                        tool_calls[tool_call_id] = tool_name

                        logger.info(
                            f"  ToolCall: {tool_name}({args})",
                            part_type="tool_call",
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                            args=args,
                        )

                    elif 'ToolReturn' in part_type:
                        # Use dataclass fields for structured logging
                        tool_name = part.tool_name
                        tool_call_id = part.tool_call_id
                        content = part.content
                        timestamp = part.timestamp
                        metadata = part.metadata

                        # Truncate large content for readability
                        content_str = str(content)
                        content_preview = content_str[:200]
                        content_size = len(content_str)

                        # Check if this return correlates with a
                        # previous call
                        correlation = tool_calls.get(tool_call_id, 'unknown')

                        ellipsis = '...' if content_size > 200 else ''
                        logger.info(
                            f"  ToolReturn [{tool_name}]: "
                            f"{content_preview}{ellipsis}",
                            part_type="tool_return",
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                            correlation_tool=correlation,
                            content_size=content_size,
                            timestamp=str(timestamp),
                            metadata=metadata,
                        )

                        # Log full content at trace level
                        logger.trace(
                            f"  ToolReturn [{tool_name}] full "
                            f"content:\n{content}",
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                        )

                    elif 'RetryPrompt' in part_type:
                        # Use dataclass fields for structured logging
                        content = part.content
                        tool_name = part.tool_name
                        tool_call_id = part.tool_call_id
                        timestamp = part.timestamp

                        # Check correlation
                        correlation = tool_calls.get(tool_call_id, 'unknown')

                        logger.warning(
                            f"  RetryPrompt [{tool_name or 'general'}]: "
                            f"{content}",
                            part_type="retry_prompt",
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                            correlation_tool=correlation,
                            timestamp=str(timestamp),
                            retry_content=str(content),
                        )

                    else:
                        logger.debug(
                            f"  {part_type}: {part}",
                            part_type=part_type.lower(),
                        )

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

        # Log prompt being sent
        logger.info(f"Sending prompt to LLM: {prompt}")

        # Log pre-call debug info
        self._log_pre_call_debug_info(workspace, prompt)

        # Create agent
        agent = self._create_agent()
        self._log_agent_debug_info(agent)

        # Run agent with workspace as dependencies using streaming
        logger.debug("Calling LLM API...")
        try:
            async with agent.run_stream(prompt, deps=workspace) as stream:
                # Get the final output
                result = await stream.get_output()
                logger.debug("LLM API call completed")

                # Log conversation history
                messages = stream.all_messages()
                self._log_message_history(messages)

                # Log result debug info
                self._log_result_debug_info(stream)

                # The agent should call submit_resolution which
                # validates and returns the content
                return result

        except Exception as e:
            # Stream is still in scope - we can access messages even
            # on failure
            try:
                messages = stream.all_messages()
                msg_count = len(messages)
                logger.error(
                    f"Logging message history from failed run "
                    f"({msg_count} messages)"
                )
                self._log_message_history(messages)
            except Exception as e2:
                logger.error(
                    f"Could not retrieve messages from failed run: {e2}"
                )

            self._log_exception_debug_info(e)
            raise


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
