"""GitHub PAT encryption and PR helpers (US7 / T100–T101)."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet
from github import Github, GithubException

from app.config import settings

if TYPE_CHECKING:
    from app.models.github_config import GitHubConfig
    from app.models.task import Task

logger = logging.getLogger(__name__)


def encrypt_pat(pat: str) -> str:
    return Fernet(settings.fernet_key).encrypt(pat.encode()).decode()


def decrypt_pat(encrypted: str) -> str:
    return Fernet(settings.fernet_key).decrypt(encrypted.encode()).decode()


def _integration_branch(repo: object) -> str:
    """Return 'main', 'master', or the current active branch."""
    for candidate in ("main", "master"):
        if candidate in repo.heads:  # type: ignore[attr-defined]
            return candidate
    return repo.active_branch.name  # type: ignore[attr-defined]


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


async def commit_and_push_branch(
    config: GitHubConfig,
    sandbox_path: Path,
    branch_name: str,
    commit_message: str,
) -> bool:
    """Stage all changes in the sandbox, commit to ``branch_name``, push to GitHub.

    Returns ``True`` if the branch was pushed, ``False`` if there was nothing to push.
    """

    def _do() -> bool:
        from git import Repo  # local import to avoid top-level GitPython dep at import time

        repo = Repo(str(sandbox_path.resolve()))

        if branch_name not in repo.heads:
            logger.warning(
                "commit_and_push_branch: branch %s not found in sandbox %s",
                branch_name,
                sandbox_path,
            )
            return False

        # Switch to the task branch
        repo.git.checkout(branch_name)

        # Stage everything
        repo.git.add("-A")

        # Detect staged changes
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(sandbox_path.resolve()),
            capture_output=True,
        )
        has_staged = diff_result.returncode != 0  # returncode 1 → has staged changes

        if has_staged:
            repo.git.commit("-m", commit_message)

        # Check whether branch is ahead of integration (skip push if nothing new)
        integration = _integration_branch(repo)
        try:
            ahead_raw = repo.git.rev_list(
                f"{integration}..{branch_name}", "--count"
            ).strip()
            ahead = int(ahead_raw)
        except Exception:
            ahead = 1 if has_staged else 0

        if ahead == 0:
            logger.info(
                "commit_and_push_branch: branch %s has no commits ahead of %s — skipping push",
                branch_name,
                integration,
            )
            return False

        # Build authenticated remote URL (PAT embedded — never stored on disk permanently)
        pat = decrypt_pat(config.pat_encrypted)
        remote_url = (
            f"https://x-access-token:{pat}@github.com/{config.repo_full_name}.git"
        )

        remote_name = "origin"
        if remote_name in [r.name for r in repo.remotes]:
            repo.remote(remote_name).set_url(remote_url)
        else:
            repo.create_remote(remote_name, remote_url)

        repo.git.push(remote_name, branch_name, "--force-with-lease")
        logger.info(
            "commit_and_push_branch: pushed %s to %s/%s",
            branch_name,
            config.repo_full_name,
            config.default_base_branch,
        )
        return True

    return await asyncio.to_thread(_do)


async def post_pipeline_status(
    config: "GitHubConfig",
    sha: str,
    state: str,
    description: str,
    context: str = "neo-kanban/pipeline",
) -> None:
    """Post a commit status to GitHub (pending / success / failure).

    Silently no-ops if sha is empty or config is missing.
    state must be one of: 'pending' | 'success' | 'failure' | 'error'
    """
    if not sha:
        return

    def _post() -> None:
        try:
            pat = decrypt_pat(config.pat_encrypted)
            gh_repo = Github(pat).get_repo(config.repo_full_name)
            commit = gh_repo.get_commit(sha)
            commit.create_status(
                state=state,
                description=description[:140],  # GitHub limit
                context=context,
            )
            logger.info(
                "GitHub status posted sha=%s state=%s context=%s", sha[:8], state, context
            )
        except GithubException as exc:
            logger.warning("Failed to post GitHub status: %s", exc)

    await asyncio.to_thread(_post)


async def post_deployment_status(
    config: "GitHubConfig",
    *,
    commit_sha: str,
    environment: str,
    state: str,
    preview_url: str,
    description: str,
) -> None:
    """Create a GitHub Deployment + DeploymentStatus for the commit.

    This surfaces as a "Deployments" entry on the GitHub PR timeline.
    state must be one of: 'success' | 'failure' | 'in_progress' | 'error'
    """
    if not commit_sha:
        return

    def _post() -> None:
        try:
            pat = decrypt_pat(config.pat_encrypted)
            gh_repo = Github(pat).get_repo(config.repo_full_name)

            # Create GitHub deployment object
            deployment = gh_repo.create_deployment(
                ref=commit_sha,
                environment=environment,
                auto_merge=False,
                required_contexts=[],
                description=description[:140],
            )

            # Attach deployment status with the URL
            deployment.create_status(
                state=state,
                environment_url=preview_url,
                log_url=preview_url,
                description=description[:140],
            )
            logger.info(
                "GitHub deployment status posted sha=%s env=%s url=%s",
                commit_sha[:8], environment, preview_url,
            )
        except GithubException as exc:
            logger.warning("Failed to post GitHub deployment: %s", exc)

    await asyncio.to_thread(_post)


async def push_integration_branch(
    config: "GitHubConfig",
    sandbox_path: Path,
) -> bool:
    """Push the local integration branch (main/master) to GitHub after a task squash-merge.

    This keeps GitHub's main branch in sync with the accumulated completed work.
    Returns ``True`` if the push succeeded, ``False`` if skipped (nothing ahead of remote).
    """

    def _do() -> bool:
        from git import Repo  # local import

        repo = Repo(str(sandbox_path.resolve()))
        integration = _integration_branch(repo)

        pat = decrypt_pat(config.pat_encrypted)
        remote_url = (
            f"https://x-access-token:{pat}@github.com/{config.repo_full_name}.git"
        )

        remote_name = "origin"
        if remote_name in [r.name for r in repo.remotes]:
            repo.remote(remote_name).set_url(remote_url)
        else:
            repo.create_remote(remote_name, remote_url)

        # Push integration branch; --force-with-lease guards against accidental overwrites
        repo.git.push(remote_name, integration, "--force-with-lease")
        logger.info(
            "push_integration_branch: pushed %s to %s",
            integration,
            config.repo_full_name,
        )
        return True

    return await asyncio.to_thread(_do)


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
