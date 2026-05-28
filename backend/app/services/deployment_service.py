"""Deployment orchestration service.

Responsibilities:
- Load DeploymentConfig for a project
- Decrypt provider token
- Dispatch to the correct adapter (Vercel / Railway)
- Update Deployment row with result
- Post GitHub deployment status
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_config import DeploymentConfig, DeployProvider

logger = logging.getLogger(__name__)


# ── Token encryption (reuse same key as GitHub PAT) ───────────────────────────

def encrypt_token(token: str) -> str:
    return Fernet(settings.fernet_key).encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return Fernet(settings.fernet_key).decrypt(encrypted.encode()).decode()


# ── Provider factory ──────────────────────────────────────────────────────────

def _get_adapter(provider: DeployProvider):
    if provider == DeployProvider.VERCEL:
        from app.adapters.vercel_adapter import VercelAdapter
        return VercelAdapter()
    if provider == DeployProvider.RAILWAY:
        from app.adapters.railway_adapter import RailwayAdapter
        return RailwayAdapter()
    return None


# ── Core deploy method ────────────────────────────────────────────────────────

async def deploy_preview(
    session: AsyncSession,
    *,
    deployment: Deployment,
    branch_name: str | None,
    commit_sha: str | None,
) -> Deployment:
    """Run preview deployment for a given Deployment row.

    Looks up the DeploymentConfig for the project, calls the provider adapter,
    and updates the Deployment row in-place.
    Returns the updated Deployment row.
    """
    config = await session.scalar(
        select(DeploymentConfig).where(
            DeploymentConfig.project_id == deployment.project_id,
            DeploymentConfig.enabled.is_(True),
        )
    )

    if config is None or config.provider == DeployProvider.NONE:
        deployment.status = DeploymentStatus.SKIPPED
        deployment.deploy_logs = "No deployment provider configured for this project."
        deployment.error_message = "No provider"
        await session.flush()
        return deployment

    adapter = _get_adapter(config.provider)
    if adapter is None:
        deployment.status = DeploymentStatus.SKIPPED
        deployment.deploy_logs = f"Unknown provider: {config.provider}"
        await session.flush()
        return deployment

    token = decrypt_token(config.token_encrypted)
    deployment.status = DeploymentStatus.DEPLOYING
    deployment.provider = str(config.provider)
    deployment.branch_name = branch_name
    deployment.commit_sha = commit_sha
    await session.flush()

    try:
        result = await adapter.deploy(
            branch_name=branch_name or "main",
            commit_sha=commit_sha,
            project_name=config.project_name,
            team_id=config.team_id,
            token=token,
        )
    except Exception as exc:
        logger.exception("Adapter deploy() raised for deployment %s", deployment.id)
        deployment.status = DeploymentStatus.DEGRADED
        deployment.error_message = str(exc)
        deployment.deploy_logs = f"Adapter error: {exc}"
        await session.flush()
        return deployment

    deployment.external_id = result.external_id
    deployment.preview_url = result.preview_url
    deployment.deploy_logs = result.logs
    deployment.duration_ms = result.duration_ms
    deployment.deployed_at = datetime.now(timezone.utc)

    if result.success:
        deployment.status = DeploymentStatus.HEALTHY
    else:
        deployment.status = DeploymentStatus.DEGRADED
        deployment.error_message = result.error_message

    await session.flush()
    return deployment


# ── Config CRUD ───────────────────────────────────────────────────────────────

async def get_config(session: AsyncSession, project_id: UUID) -> DeploymentConfig | None:
    return await session.scalar(
        select(DeploymentConfig).where(DeploymentConfig.project_id == project_id)
    )


async def upsert_config(
    session: AsyncSession,
    *,
    project_id: UUID,
    provider: str,
    token: str,
    project_name: str,
    team_id: str | None,
    base_url: str | None,
    enabled: bool = True,
) -> DeploymentConfig:
    existing = await get_config(session, project_id)
    encrypted = encrypt_token(token)

    if existing is not None:
        existing.provider = DeployProvider(provider)
        existing.token_encrypted = encrypted
        existing.project_name = project_name
        existing.team_id = team_id
        existing.base_url = base_url
        existing.enabled = enabled
        existing.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return existing

    cfg = DeploymentConfig(
        project_id=project_id,
        provider=DeployProvider(provider),
        token_encrypted=encrypted,
        project_name=project_name,
        team_id=team_id,
        base_url=base_url,
        enabled=enabled,
    )
    session.add(cfg)
    await session.flush()
    return cfg


async def test_config(
    *,
    provider: str,
    token: str,
    project_name: str,
    team_id: str | None,
) -> tuple[bool, str]:
    """Quick connectivity check — returns (ok, message)."""
    if provider == "vercel":
        try:
            import httpx
            headers = {"Authorization": f"Bearer {token}"}
            params: dict = {}
            if team_id:
                params["teamId"] = team_id
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.vercel.com/v9/projects/{project_name}",
                    headers=headers,
                    params=params,
                )
            if resp.status_code == 200:
                return True, f"Vercel project '{resp.json().get('name', project_name)}' found."
            return False, f"Vercel returned HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            return False, f"Connection error: {exc}"

    if provider == "railway":
        try:
            import httpx
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            query = """query { me { email } }"""
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://backboard.railway.app/graphql/v2",
                    headers=headers,
                    json={"query": query},
                )
            if resp.status_code == 200 and not resp.json().get("errors"):
                email = (resp.json().get("data") or {}).get("me", {}).get("email", "unknown")
                return True, f"Railway token valid. Authenticated as: {email}"
            return False, f"Railway error: {resp.text[:200]}"
        except Exception as exc:
            return False, f"Connection error: {exc}"

    return False, f"Unknown provider: {provider}"
