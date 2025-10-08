#!/usr/bin/env python3
"""Splintercat MVP - LLM-assisted git merge conflict resolution."""

import os
import sys
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.core.command_runner import CommandRunner
from src.core.config import Settings
from src.core.log import logger, setup_logging


def get_conflicted_files(runner, workdir):
    """Get list of files with merge conflicts."""
    result = runner.run(
        ["git", "-C", str(workdir), "diff", "--name-only", "--diff-filter=U"],
        check=False,
    )
    if not result.stdout.strip():
        return []
    files = result.stdout.strip().split("\n")
    return [f for f in files if f]


def read_conflict(workdir, filepath):
    """Read file with conflict markers."""
    full_path = Path(workdir) / filepath
    return full_path.read_text()


def resolve_conflict_with_llm(llm, filepath, content):
    """Ask LLM to resolve merge conflict."""
    prompt = f"""You are resolving a git merge conflict in file: {filepath}

The file contains conflict markers like this:
<<<<<<< HEAD
... current code ...
=======
... incoming code ...
>>>>>>> branch-name

Your task: Provide the COMPLETE resolved file content with ALL conflict markers removed.

Rules:
- Output ONLY the resolved file content
- NO explanations, NO markdown code blocks, NO preamble
- Remove ALL conflict markers (<<<<<<< ======= >>>>>>>)
- Preserve all code that should remain
- Choose the best resolution (keep one side, merge both, or rewrite)

File content:
{content}
"""

    response = llm.invoke(prompt)
    return response.content


def main():
    """Main entry point."""
    settings = Settings()
    setup_logging(settings.verbose)

    runner = CommandRunner(interactive=settings.interactive)
    workdir = settings.target.workdir
    source_ref = os.getenv("SOURCE_REF", "heaven/main")

    # Get LLM config from environment
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY environment variable not set")
        sys.exit(1)

    model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

    logger.info(f"Starting merge of {source_ref} into {workdir}")

    # Initialize LLM
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    # Attempt merge
    logger.info(f"Attempting: git merge {source_ref} --no-commit")
    result = runner.run(
        ["git", "-C", str(workdir), "merge", source_ref, "--no-commit"],
        check=False
    )

    if result.success:
        logger.success("Merge completed without conflicts!")
        runner.run(["git", "-C", str(workdir), "commit", "-m", f"Merge {source_ref}"])
        return

    # Handle conflicts
    conflicted_files = get_conflicted_files(runner, workdir)
    logger.warning(f"Found {len(conflicted_files)} conflicted files")

    for filepath in conflicted_files:
        logger.info(f"Resolving conflict in {filepath}")

        content = read_conflict(workdir, filepath)
        resolved = resolve_conflict_with_llm(llm, filepath, content)

        # Write resolution
        full_path = Path(workdir) / filepath
        full_path.write_text(resolved)

        # Stage file
        runner.run(["git", "-C", str(workdir), "add", filepath])
        logger.success(f"Resolved and staged {filepath}")

    # Commit the merge
    logger.info("Committing merge...")
    runner.run(
        ["git", "-C", str(workdir), "commit", "-m", f"Merge {source_ref} with LLM assistance"]
    )
    logger.success("Merge complete!")


if __name__ == "__main__":
    main()
