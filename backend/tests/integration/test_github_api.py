"""Integration tests: GitHub API (US7 / T102)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.services import github_service
from tests.integration.helpers import create_project


@pytest.mark.asyncio
async def test_github_config_get_and_upsert(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)

    r = await test_client.get(f"/api/v1/projects/{pid}/github", headers=auth_headers)
    assert r.status_code == 404

    with patch(
        "app.api.v1.github.github_service.validate_config",
        AsyncMock(return_value=False),
    ):
        r = await test_client.put(
            f"/api/v1/projects/{pid}/github",
            headers=auth_headers,
            json={
                "repo_full_name": "owner/repo",
                "pat": "ghp_invalid",
                "default_base_branch": "main",
            },
        )
    assert r.status_code == 422

    with patch(
        "app.api.v1.github.github_service.validate_config",
        AsyncMock(return_value=True),
    ):
        r = await test_client.put(
            f"/api/v1/projects/{pid}/github",
            headers=auth_headers,
            json={
                "repo_full_name": "owner/repo",
                "pat": "ghp_valid_token",
                "default_base_branch": "develop",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["repo_full_name"] == "owner/repo"
    assert body["default_base_branch"] == "develop"
    assert body["enabled"] is True
    assert "pat" not in body

    r = await test_client.get(f"/api/v1/projects/{pid}/github", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["repo_full_name"] == "owner/repo"

    with patch(
        "app.api.v1.github.github_service.validate_config",
        AsyncMock(return_value=True),
    ):
        r = await test_client.put(
            f"/api/v1/projects/{pid}/github",
            headers=auth_headers,
            json={
                "repo_full_name": "owner/updated",
                "pat": "ghp_new_token",
                "default_base_branch": "main",
            },
        )
    assert r.status_code == 200
    assert r.json()["repo_full_name"] == "owner/updated"


@pytest.mark.asyncio
async def test_github_encrypt_roundtrip_via_api(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    pat = "ghp_roundtrip_secret"

    with patch(
        "app.api.v1.github.github_service.validate_config",
        AsyncMock(return_value=True),
    ):
        r = await test_client.put(
            f"/api/v1/projects/{pid}/github",
            headers=auth_headers,
            json={
                "repo_full_name": "owner/repo",
                "pat": pat,
                "default_base_branch": "main",
            },
        )
    assert r.status_code == 200

    from sqlalchemy import text

    from app.database import engine

    async with engine.begin() as conn:
        res = await conn.execute(
            text("SELECT pat_encrypted FROM github_configs WHERE project_id = :pid"),
            {"pid": pid},
        )
        encrypted = res.scalar_one()
    assert github_service.decrypt_pat(encrypted) == pat


@pytest.mark.asyncio
async def test_github_requires_auth(test_client: AsyncClient) -> None:
    fake = UUID("00000000-0000-0000-0000-000000000001")
    r = await test_client.get(f"/api/v1/projects/{fake}/github")
    assert r.status_code == 401
