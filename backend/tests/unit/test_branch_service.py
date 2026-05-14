"""Unit tests for ``branch_service`` (US15 / T102)."""

from __future__ import annotations

from uuid import UUID

from app.git.branch_service import task_branch_slug


def test_task_branch_slug() -> None:
    tid = UUID("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")
    assert task_branch_slug(tid) == "task/aaaaaaaa"
