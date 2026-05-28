"""Railway deployment adapter.

Uses Railway's GraphQL API v2 to trigger service deployments.

Docs: https://docs.railway.app/reference/public-api

Authentication: Bearer token (Railway API token).

Strategy:
  - Use `serviceInstanceDeploy` mutation to trigger a redeployment
  - Poll `deployment` query for status (BUILDING → SUCCESS / FAILED)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from app.adapters.base import BaseDeployAdapter, DeployResult

logger = logging.getLogger(__name__)

_RAILWAY_GQL = "https://backboard.railway.app/graphql/v2"
_POLL_INTERVAL = 6
_POLL_MAX = 20       # 20 × 6s = 2 minutes
_MAX_LOG = 8_192


_TRIGGER_MUTATION = """
mutation RedeplployService($serviceId: String!, $environmentId: String) {
  serviceInstanceDeploy(serviceId: $serviceId, environmentId: $environmentId)
}
"""

_DEPLOYMENTS_QUERY = """
query GetDeployments($serviceId: String!) {
  deployments(input: { serviceId: $serviceId }, first: 1) {
    edges {
      node {
        id
        status
        url
        createdAt
      }
    }
  }
}
"""


class RailwayAdapter(BaseDeployAdapter):
    """Deploy to Railway via GraphQL API."""

    async def deploy(
        self,
        *,
        branch_name: str,
        commit_sha: str | None,
        project_name: str,
        team_id: str | None,
        token: str,
    ) -> DeployResult:
        """
        project_name is treated as the Railway service ID.
        team_id is the Railway environment ID (optional).
        """
        t0 = time.monotonic()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Trigger redeployment
        variables: dict[str, Any] = {"serviceId": project_name}
        if team_id:
            variables["environmentId"] = team_id

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    _RAILWAY_GQL,
                    headers=headers,
                    json={"query": _TRIGGER_MUTATION, "variables": variables},
                )
        except httpx.RequestError as exc:
            dur = int((time.monotonic() - t0) * 1000)
            return DeployResult(
                success=False, external_id="", preview_url="",
                logs=f"Network error: {exc}", duration_ms=dur,
                error_message=str(exc),
            )

        if resp.status_code != 200:
            dur = int((time.monotonic() - t0) * 1000)
            body = resp.text[:2000]
            return DeployResult(
                success=False, external_id="", preview_url="",
                logs=f"Railway API error {resp.status_code}:\n{body}",
                duration_ms=dur,
                error_message=f"HTTP {resp.status_code}: {body[:200]}",
            )

        gql_data = resp.json()
        errors = gql_data.get("errors")
        if errors:
            dur = int((time.monotonic() - t0) * 1000)
            msg = str(errors[0].get("message", "Unknown GQL error"))
            return DeployResult(
                success=False, external_id="", preview_url="",
                logs=f"Railway GQL error: {msg}", duration_ms=dur,
                error_message=msg,
            )

        logs_acc: list[str] = ["Railway redeployment triggered."]

        # Poll latest deployment for status
        deployment_id = ""
        preview_url = ""
        final_status = "BUILDING"
        for _ in range(_POLL_MAX):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(
                        _RAILWAY_GQL,
                        headers=headers,
                        json={"query": _DEPLOYMENTS_QUERY, "variables": {"serviceId": project_name}},
                    )
                if r.status_code == 200:
                    rdata = r.json()
                    edges = (rdata.get("data") or {}).get("deployments", {}).get("edges", [])
                    if edges:
                        node = edges[0]["node"]
                        deployment_id = node.get("id", deployment_id)
                        preview_url = node.get("url") or ""
                        if preview_url and not preview_url.startswith("http"):
                            preview_url = f"https://{preview_url}"
                        final_status = node.get("status", final_status)
                        logs_acc.append(f"  → {final_status}")
                        if final_status in ("SUCCESS", "FAILED", "CRASHED", "REMOVED"):
                            break
            except Exception as exc:
                logs_acc.append(f"  (poll error: {exc})")

        dur = int((time.monotonic() - t0) * 1000)
        success = final_status == "SUCCESS"
        return DeployResult(
            success=success,
            external_id=deployment_id,
            preview_url=preview_url,
            logs="\n".join(logs_acc)[:_MAX_LOG],
            duration_ms=dur,
            error_message="" if success else f"Railway deployment ended in state: {final_status}",
        )

    async def get_deployment_status(
        self,
        *,
        external_id: str,
        token: str,
        team_id: str | None = None,
    ) -> str:
        # Railway doesn't have a single-deployment-by-ID query in public API easily,
        # so we just return a best-effort based on stored state.
        return "deploying"


def _map_railway_status(status: str) -> str:
    mapping = {
        "SUCCESS": "healthy",
        "FAILED": "degraded",
        "CRASHED": "degraded",
        "REMOVED": "degraded",
        "BUILDING": "deploying",
        "DEPLOYING": "deploying",
        "INITIALIZING": "deploying",
    }
    return mapping.get(status.upper(), "deploying")
