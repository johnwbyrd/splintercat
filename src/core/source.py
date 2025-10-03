"""Source ABC and GitSource implementation for fetching patches."""

from abc import ABC, abstractmethod

from src.core.command_runner import CommandRunner
from src.core.config import SourceConfig
from src.core.log import logger
from src.core.patch import Patch
from src.patchset import PatchSet


class Source(ABC):
    """Abstract base class for patch sources."""

    @abstractmethod
    def get_patches(self) -> PatchSet:
        """Fetch patches from the source.

        Returns:
            PatchSet containing patches
        """


class GitSource(Source):
    """Fetches patches from a git repository using git format-patch."""

    def __init__(self, config: SourceConfig, runner: CommandRunner, log_truncate_length: int = 60):
        """Initialize GitSource.

        Args:
            config: Source configuration with repo, branch, workdir, and commands
            runner: CommandRunner instance for executing git commands
            log_truncate_length: Max length for patch subjects in logs
        """
        self.config = config
        self.runner = runner
        self.log_truncate_length = log_truncate_length

    def get_patches(self) -> PatchSet:
        """Fetch patches from git repository.

        Workflow:
        1. Fetch from remote
        2. Find merge-base between HEAD and FETCH_HEAD
        3. List commits chronologically from merge-base forward
        4. Generate patches using git format-patch

        Returns:
            RangePatchSet containing patches in chronological order
        """
        # Fetch latest from upstream
        logger.info(f"Fetching from {self.config.repo} {self.config.branch}")
        self.runner.run(self.config.commands.fetch.format(**self.config.model_dump()))

        # Find merge-base
        result = self.runner.run(
            self.config.commands.merge_base.format(**self.config.model_dump())
        )
        merge_base = result.stdout.strip()

        if not merge_base:
            logger.warning("No merge-base found, no patches to fetch")
            return PatchSet([])

        logger.debug(f"Merge-base: {merge_base}")

        # Prepare limit flag for head command
        limit_flag = f" | head -n {self.config.limit}" if self.config.limit else ""

        # List commits from merge-base forward
        result = self.runner.run(
            self.config.commands.list_commits.format(
                merge_base=merge_base, limit_flag=limit_flag, **self.config.model_dump()
            )
        )
        commit_list = result.stdout.strip()

        if not commit_list:
            logger.info("No new commits to process")
            return PatchSet([])

        commits = commit_list.split("\n")
        logger.info(f"Found {len(commits)} commits to process")

        # Generate patches for each commit
        patches = []
        for commit in commits:
            result = self.runner.run(
                self.config.commands.format_patch.format(
                    commit=commit, **self.config.model_dump()
                ),
                log_level="DEBUG",
            )
            if result.stdout:
                patch = Patch(id=commit, diff=result.stdout)
                patches.append(patch)
                logger.info(
                    f"Generated patch for {commit[:8]}: {patch.subject[:self.log_truncate_length]}"
                )

        logger.success(f"Generated {len(patches)} patches")
        return PatchSet(patches)
