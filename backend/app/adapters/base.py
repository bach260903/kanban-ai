"""Abstract deployment adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeployResult:
    """Returned by every provider adapter after a deploy attempt."""
    success: bool
    external_id: str         # provider-side deployment ID
    preview_url: str         # public URL for the deployment
    logs: str                # deployment log output (truncated)
    duration_ms: int
    error_message: str = ""  # non-empty on failure


class BaseDeployAdapter(ABC):
    """Every provider adapter must implement this interface."""

    @abstractmethod
    async def deploy(
        self,
        *,
        branch_name: str,
        commit_sha: str | None,
        project_name: str,
        team_id: str | None,
        token: str,
    ) -> DeployResult:
        """Trigger a deployment and return the result."""

    @abstractmethod
    async def get_deployment_status(
        self,
        *,
        external_id: str,
        token: str,
        team_id: str | None = None,
    ) -> str:
        """Return current deployment status: 'deploying' | 'healthy' | 'degraded'."""
