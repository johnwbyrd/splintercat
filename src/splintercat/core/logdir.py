"""Agent log directory management."""

from datetime import datetime
from pathlib import Path


class AgentLogDir:
    """Manages per-execution log directories for agent traces."""

    def __init__(
        self, base_dir: Path, command: str, project_name: str | None = None
    ):
        """Create a new log directory for this execution.

        Args:
            base_dir: Base directory for all agent logs
            command: Command name (merge, reset, etc.)
            project_name: Optional project name for subdirectory
                organization
        """
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

        # Add project subdirectory if provided
        if project_name:
            base_dir = base_dir / project_name

        self.run_dir = base_dir / f"{command}-{timestamp}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.run_dir / "agent.log"

    def get_log_file(self) -> Path:
        """Get the log file path for this execution.

        Returns:
            Path to the agent log file for this run
        """
        return self.log_file
