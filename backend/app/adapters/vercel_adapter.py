"""Vercel deployment adapter.

Uses Vercel REST API v13 to trigger and monitor deployments.

Docs: https://vercel.com/docs/rest-api/endpoints/deployments

Authentication: Bearer token (personal or team access token).

Deployment strategy:
  - If the Vercel project is connected to GitHub: use `gitSource` with branch name
    → Vercel picks up the branch automatically from GitHub
  - Polling: Vercel deployments typically go READY within 30–120s
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.adapters.base import BaseDeployAdapter, DeployResult

logger = logging.getLogger(__name__)

_VERCEL_API = "https://api.vercel.com"
_POLL_INTERVAL = 5    # seconds between status polls
_POLL_MAX = 24        # 24 × 5s = 2 minutes max wait
_MAX_LOG = 8_192      # max bytes of deploy logs to store


class VercelAdapter(BaseDeployAdapter):
    """Deploy to Vercel via their REST API using a git-connected project."""

    async def deploy(
        self,
        *,
        branch_name: str,
        commit_sha: str | None,
        project_name: str,
        team_id: str | None,
        token: str,
    ) -> DeployResult:
        t0 = time.monotonic()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params: dict[str, str] = {}
        if team_id:
            params["teamId"] = team_id

        # Fetch project info to get repoId + productionBranch (required by Vercel API v13)
        repo_id: int | None = None
        production_branch: str = branch_name
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                proj_resp = await client.get(
                    f"{_VERCEL_API}/v9/projects/{project_name}",
                    headers=headers,
                    params=params,
                )
            if proj_resp.status_code == 200:
                link = proj_resp.json().get("link") or {}
                repo_id = link.get("repoId")
                production_branch = link.get("productionBranch") or branch_name
        except Exception as exc:
            logger.warning("vercel_adapter: failed to fetch project info: %s", exc)

        # Use production branch — sandbox branches are local and not pushed to GitHub
        deploy_ref = production_branch

        # Trigger deployment from git branch
        git_source: dict = {
            "type": "github",
            "ref": deploy_ref,
        }
        if repo_id is not None:
            git_source["repoId"] = repo_id

        payload: dict = {
            "name": project_name,
            "gitSource": git_source,
            "target": "production",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_VERCEL_API}/v13/deployments",
                    headers=headers,
                    params=params,
                    json=payload,
                )
        except httpx.RequestError as exc:
            dur = int((time.monotonic() - t0) * 1000)
            return DeployResult(
                success=False,
                external_id="",
                preview_url="",
                logs=f"Network error: {exc}",
                duration_ms=dur,
                error_message=str(exc),
            )

        if resp.status_code not in (200, 201):
            dur = int((time.monotonic() - t0) * 1000)
            body = resp.text[:2000]
            return DeployResult(
                success=False,
                external_id="",
                preview_url="",
                logs=f"Vercel API error {resp.status_code}:\n{body}",
                duration_ms=dur,
                error_message=f"HTTP {resp.status_code}: {body[:200]}",
            )

        data = resp.json()
        deployment_id = data.get("id", "")
        url = data.get("url", "")
        if url and not url.startswith("http"):
            url = f"https://{url}"
        initial_state = data.get("readyState", "BUILDING")

        # Poll until READY or ERROR
        logs_acc: list[str] = [f"Deployment created: {deployment_id}  state={initial_state}"]
        final_state = initial_state
        for _ in range(_POLL_MAX):
            if final_state in ("READY", "ERROR", "CANCELED"):
                break
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    status_resp = await client.get(
                        f"{_VERCEL_API}/v13/deployments/{deployment_id}",
                        headers=headers,
                        params=params,
                    )
                if status_resp.status_code == 200:
                    sdata = status_resp.json()
                    final_state = sdata.get("readyState", final_state)
                    logs_acc.append(f"  → {final_state}")
            except Exception as exc:
                logs_acc.append(f"  (poll error: {exc})")

        dur = int((time.monotonic() - t0) * 1000)
        logs_text = "\n".join(logs_acc)[:_MAX_LOG]
        success = final_state == "READY"
        return DeployResult(
            success=success,
            external_id=deployment_id,
            preview_url=url,
            logs=logs_text,
            duration_ms=dur,
            error_message="" if success else f"Vercel deployment ended in state: {final_state}",
        )

    async def get_deployment_status(
        self,
        *,
        external_id: str,
        token: str,
        team_id: str | None = None,
    ) -> str:
        headers = {"Authorization": f"Bearer {token}"}
        params: dict[str, str] = {}
        if team_id:
            params["teamId"] = team_id
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_VERCEL_API}/v13/deployments/{external_id}",
                    headers=headers,
                    params=params,
                )
            if resp.status_code == 200:
                state = resp.json().get("readyState", "BUILDING")
                return _map_vercel_state(state)
        except Exception:
            logger.debug("Vercel status check failed", exc_info=True)
        return "deploying"


def _map_vercel_state(state: str) -> str:
    mapping = {
        "READY": "healthy",
        "ERROR": "degraded",
        "CANCELED": "degraded",
        "BUILDING": "deploying",
        "INITIALIZING": "deploying",
        "QUEUED": "deploying",
    }
    return mapping.get(state.upper(), "deploying")
