"""GitHub PAT encryption and PR helpers (US7 / T100–T101)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from github import Github, GithubException

from app.config import settings

if TYPE_CHECKING:
    from app.models.github_config import GitHubConfig
    from app.models.task import Task


def encrypt_pat(pat: str) -> str:
    return Fernet(settings.fernet_key).encrypt(pat.encode()).decode()


def decrypt_pat(encrypted: str) -> str:
    return Fernet(settings.fernet_key).decrypt(encrypted.encode()).decode()


async def validate_config(repo_full_name: str, pat: str) -> bool:
    def _check() -> bool:
        try:
            Github(pat).get_repo(repo_full_name)
            return True
        except GithubException:
            return False
        except Exception:
            return False

    return await asyncio.to_thread(_check)


async def create_pull_request(
    config: GitHubConfig,
    task: Task,
    diff_content: str,
    branch_name: str,
) -> str:
    def _create() -> str:
        pat = decrypt_pat(config.pat_encrypted)
        repo = Github(pat).get_repo(config.repo_full_name)
        pr = repo.create_pull(
            title=task.title,
            body=(
                f"## {task.title}\n\n"
                f"{task.description or ''}\n\n"
                f"```diff\n{diff_content[:3000]}\n```"
            ),
            head=branch_name,
            base=config.default_base_branch,
        )
        return pr.html_url

    return await asyncio.to_thread(_create)
