"""Unit tests for GitHub service (US7 / T100–T101)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_config import GitHubConfig
from app.models.task import Task, TaskStatus
from app.services import github_service


def test_encrypt_decrypt_pat_roundtrip() -> None:
    pat = "ghp_test_token_12345"
    encrypted = github_service.encrypt_pat(pat)
    assert encrypted != pat
    assert github_service.decrypt_pat(encrypted) == pat


@pytest.mark.asyncio
async def test_validate_config_success() -> None:
    mock_repo = MagicMock()
    with patch("app.services.github_service.Github") as github_cls:
        github_cls.return_value.get_repo.return_value = mock_repo
        ok = await github_service.validate_config("owner/repo", "ghp_token")
    assert ok is True
    github_cls.return_value.get_repo.assert_called_once_with("owner/repo")


@pytest.mark.asyncio
async def test_validate_config_failure() -> None:
    from github import GithubException

    with patch("app.services.github_service.Github") as github_cls:
        github_cls.return_value.get_repo.side_effect = GithubException(404, {}, None)
        ok = await github_service.validate_config("owner/missing", "ghp_token")
    assert ok is False


@pytest.mark.asyncio
async def test_validate_config_handles_network_errors() -> None:
    with patch("app.services.github_service.Github") as github_cls:
        github_cls.return_value.get_repo.side_effect = ConnectionError("offline")
        ok = await github_service.validate_config("owner/repo", "ghp_token")
    assert ok is False


@pytest_asyncio.fixture
async def github_task(async_db_session: AsyncSession) -> tuple[GitHubConfig, Task]:
    project_res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES (:name, 'test', 'python', '', 'active')
            RETURNING id
            """
        ),
        {"name": f"GitHub Project {uuid.uuid4().hex[:8]}"},
    )
    project_id = project_res.scalar_one()
    config = GitHubConfig(
        project_id=project_id,
        repo_full_name="owner/repo",
        pat_encrypted=github_service.encrypt_pat("ghp_test"),
        default_base_branch="main",
        enabled=True,
    )
    task = Task(
        project_id=project_id,
        title="Add feature",
        description="Implement it",
        status=TaskStatus.DONE,
        priority=0,
    )
    async_db_session.add(config)
    async_db_session.add(task)
    await async_db_session.flush()
    return config, task


@pytest.mark.asyncio
async def test_create_pull_request_returns_url(github_task: tuple[GitHubConfig, Task]) -> None:
    config, task = github_task
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/owner/repo/pull/1"
    mock_repo = MagicMock()
    mock_repo.create_pull.return_value = mock_pr

    with (
        patch("app.services.github_service.Github") as github_cls,
        patch("app.services.github_service.decrypt_pat", return_value="ghp_test"),
    ):
        github_cls.return_value.get_repo.return_value = mock_repo
        url = await github_service.create_pull_request(
            config,
            task,
            "diff line",
            "feature-branch",
        )

    assert url == "https://github.com/owner/repo/pull/1"
    mock_repo.create_pull.assert_called_once()
    call_kwargs = mock_repo.create_pull.call_args.kwargs
    assert call_kwargs["title"] == task.title
    assert call_kwargs["head"] == "feature-branch"
    assert call_kwargs["base"] == "main"
