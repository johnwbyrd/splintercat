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
    """Fetches commits from a git repository for cherry-picking."""

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
        4. Create Patch objects with commit SHAs (no diff generation needed for cherry-pick)

        Returns:
            PatchSet containing patches in chronological order
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

        # Create patch objects for each commit
        patches = []
        for commit in commits:
            # Get commit info for logging (subject, author, date)
            result = self.runner.run(
                self.config.commands.get_commit_info.format(
                    commit=commit, **self.config.model_dump()
                ),
                log_level="DEBUG",
            )

            # Parse commit info
            info = {}
            for line in result.stdout.strip().split("\n"):
                if ": " in line:
                    key, value = line.split(": ", 1)
                    info[key.lower()] = value

            # Create patch with commit SHA (no diff needed for cherry-pick)
            patch = Patch(id=commit, diff="", metadata=info)
            patches.append(patch)

            subject = info.get("subject", "")[:self.log_truncate_length]
            logger.info(f"Found commit {commit[:8]}: {subject}")

        logger.success(f"Collected {len(patches)} commits for cherry-pick")
        return PatchSet(patches)
