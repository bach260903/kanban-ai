"""TC-12 (T116): squash merge adds exactly one commit on integration branch."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from git import Repo

from app.git.branch_service import _sync_ensure_task_branch, _sync_squash_merge_to_integration


@pytest.mark.skipif(not shutil.which("git"), reason="git binary not on PATH")
def test_tc12_squash_merge_adds_single_commit_on_main(tmp_path: Path) -> None:
    repo = Repo.init(tmp_path, initial_branch="main")
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "pytest")
        cw.set_value("user", "email", "pytest@example.com")

    (tmp_path / "README.md").write_text("init\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("initial")

    branch_name = "task/12345678"
    _sync_ensure_task_branch(tmp_path, branch_name)

    for i in range(3):
        (tmp_path / f"feat_{i}.py").write_text(f"x = {i}\n", encoding="utf-8")
        repo.index.add([f"feat_{i}.py"])
        repo.index.commit(f"wip {i}")

    n_before = int(repo.git.rev_list("--count", "main"))

    _sync_squash_merge_to_integration(tmp_path, branch_name)

    n_after = int(repo.git.rev_list("--count", "main"))
    assert n_after == n_before + 1, "squash merge must add exactly one commit on main (TC-12)"
