"""Tool system for LLM-based conflict resolution."""

import time
from functools import wraps

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from splintercat.core.log import logger
from splintercat.tools.base import Tool
from splintercat.tools.commands import list_allowed_commands, run_command
from splintercat.tools.registry import ToolRegistry
from splintercat.tools.workspace import (
    Workspace,
    concatenate_to_file,
    read_file,
    submit_resolution,
    write_file,
)


def _log_tool_execution(func):
    """Comprehensive tool execution logger with pre/post/error logging.

    Logs tool execution at all stages:
    - BEFORE: tool name, arguments, workspace context
    - ON SUCCESS: return value, execution time
    - ON ModelRetry: retry message with context
    - ON ERROR: full exception with traceback

    Provides complete visibility into tool interactions for debugging
    failed resolutions.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = time.time()

        # Extract workspace context if available
        workspace_info = {}
        if args and isinstance(args[0], RunContext):
            ctx = args[0]
            if hasattr(ctx, 'deps') and isinstance(ctx.deps, Workspace):
                workspace_info = {
                    'workspace_workdir': str(ctx.deps.workdir),
                    'conflict_files': ctx.deps.conflict_files,
                }

        # Log tool invocation with structured attributes
        logger.info(
            f"Tool '{tool_name}' invoked",
            tool_name=tool_name,
            args=args[1:] if len(args) > 1 else [],
            kwargs=kwargs,
            **workspace_info,
        )

        try:
            # Execute tool
            result = func(*args, **kwargs)

            # Log successful execution
            execution_time = time.time() - start_time
            result_preview = str(result)[:200] if result else ""
            result_size = len(str(result)) if result else 0

            logger.info(
                f"Tool '{tool_name}' succeeded",
                tool_name=tool_name,
                execution_time_ms=round(execution_time * 1000, 2),
                result_size=result_size,
                result_preview=result_preview,
            )

            # Log full result at trace level for detailed debugging
            logger.trace(
                f"Tool '{tool_name}' full result:\n{result}",
                tool_name=tool_name,
            )

            return result

        except ModelRetry as e:
            # Log retry with context - these are validation failures
            # or expected errors that the LLM should handle
            execution_time = time.time() - start_time

            logger.warning(
                f"Tool '{tool_name}' raised ModelRetry",
                tool_name=tool_name,
                execution_time_ms=round(execution_time * 1000, 2),
                retry_message=str(e),
                args=args[1:] if len(args) > 1 else [],
                kwargs=kwargs,
                **workspace_info,
            )

            # Re-raise to let pydantic-ai handle the retry
            raise

        except Exception as e:
            # Log unexpected errors with full context
            execution_time = time.time() - start_time

            logger.error(
                f"Tool '{tool_name}' raised unexpected exception",
                tool_name=tool_name,
                execution_time_ms=round(execution_time * 1000, 2),
                exception_type=type(e).__name__,
                exception_message=str(e),
                args=args[1:] if len(args) > 1 else [],
                kwargs=kwargs,
                _exc_info=e,
                **workspace_info,
            )

            # Re-raise to let caller handle
            raise

    return wrapper


# Apply logging decorator to all workspace tools centrally
_raw_tools = [
    run_command,
    list_allowed_commands,
    read_file,
    write_file,
    concatenate_to_file,
    submit_resolution,
]

# Workspace tools list for use with Agent(tools=[...])
# All tools are automatically wrapped with comprehensive execution
# logging
workspace_tools = [_log_tool_execution(tool) for tool in _raw_tools]

__all__ = [
    "Tool",
    "ToolRegistry",
    "workspace_tools",
    "run_command",
    "list_allowed_commands",
    "read_file",
    "write_file",
    "concatenate_to_file",
    "submit_resolution",
]
