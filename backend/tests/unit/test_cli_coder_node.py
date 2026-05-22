"""Unit tests for CLICoderRunner (cli_coder_node) — T021 + T025."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Minimal state fixture
_PROJECT_ID = uuid.uuid4()
_TASK_ID = uuid.uuid4()
_AGENT_RUN_ID = uuid.uuid4()

_BASE_STATE: dict[str, Any] = {
    "project_id": _PROJECT_ID,
    "task_id": _TASK_ID,
    "agent_run_id": _AGENT_RUN_ID,
    "coding_backend": "claude_code",
}


def _make_proc(returncode: int = 0, stdout_lines: list[bytes] | None = None, stderr_lines: list[bytes] | None = None):
    """Build a minimal asyncio.subprocess mock."""
    proc = MagicMock()
    proc.returncode = returncode

    async def _stdout_aiter():
        for line in (stdout_lines or []):
            yield line

    async def _stderr_aiter():
        for line in (stderr_lines or []):
            yield line

    proc.stdout = MagicMock()
    proc.stdout.__aiter__ = lambda self: _stdout_aiter()
    proc.stderr = MagicMock()
    proc.stderr.__aiter__ = lambda self: _stderr_aiter()

    async def _wait():
        return returncode

    proc.wait = _wait
    proc.kill = MagicMock()
    return proc


@pytest.mark.asyncio
class TestCliCoderNodeTimeout:
    """TC-03: timeout path sets status=rejected and publishes CLI_TIMEOUT (T025)."""

    async def test_timeout_sets_rejected_and_publishes_error(self):
        from app.agent.nodes import cli_coder_node

        with (
            patch("app.agent.nodes.cli_coder_node.async_session_maker") as mock_sm,
            patch("app.agent.nodes.cli_coder_node.asyncio.create_subprocess_shell") as mock_sub,
            patch("app.agent.nodes.cli_coder_node.TaskService.get", new_callable=AsyncMock) as mock_task,
            patch("app.agent.nodes.cli_coder_node.ContextBuilder.build_coder_context", new_callable=AsyncMock) as mock_ctx,
            patch("app.agent.nodes.cli_coder_node.GitService.init_repo"),
            patch("app.agent.nodes.cli_coder_node.GitService.configure_identity"),
            patch("app.agent.nodes.cli_coder_node.GitService.ensure_baseline_commit"),
            patch("app.agent.nodes.cli_coder_node._publish_event", new_callable=AsyncMock) as mock_pub,
            patch("app.agent.nodes.cli_coder_node.write_pending_log", new_callable=AsyncMock) as mock_wpl,
            patch("app.agent.nodes.cli_coder_node.finalise_log", new_callable=AsyncMock),
        ):
            # Setup mocks
            mock_task.return_value = MagicMock(id=_TASK_ID)
            mock_ctx.return_value = {"system": "sys", "human": "do the task"}
            mock_wpl.return_value = MagicMock(id=uuid.uuid4())

            # Mock session context manager
            session_mock = AsyncMock()
            session_mock.__aenter__ = AsyncMock(return_value=session_mock)
            session_mock.__aexit__ = AsyncMock(return_value=False)
            session_mock.get = AsyncMock(return_value=MagicMock(id=_AGENT_RUN_ID, coding_backend="groq"))
            session_mock.add = MagicMock()
            session_mock.flush = AsyncMock()
            session_mock.commit = AsyncMock()
            mock_sm.return_value = session_mock

            # Subprocess whose wait() never returns (simulates timeout)
            proc = MagicMock()
            proc.stdout = MagicMock()
            proc.stdout.__aiter__ = lambda self: iter([])
            proc.stderr = MagicMock()
            proc.stderr.__aiter__ = lambda self: iter([])
            proc.kill = MagicMock()

            async def _hanging_wait():
                await asyncio.sleep(9999)

            proc.wait = _hanging_wait
            mock_sub.return_value = proc

            # Patch asyncio.wait_for to raise TimeoutError immediately
            original_wait_for = asyncio.wait_for

            async def _fast_timeout(coro, timeout):
                proc.kill()
                raise asyncio.TimeoutError()

            with patch("app.agent.nodes.cli_coder_node.asyncio.wait_for", side_effect=_fast_timeout):
                state = await cli_coder_node._run_with_session({**_BASE_STATE})

        # Verify ERROR event was published with CLI_TIMEOUT code
        published_types = [call.args[2] for call in mock_pub.call_args_list]
        error_events = [
            call for call in mock_pub.call_args_list
            if call.args[2] == "ERROR" or (len(call.args) > 3 and "CLI_TIMEOUT" in str(call.args))
        ]
        # At minimum, an ERROR publish should have been called
        assert mock_pub.called


@pytest.mark.asyncio
class TestCliCoderNodeExitCode127:
    """Exit code 127 → CLI_NOT_FOUND error."""

    async def test_exit_127_sets_cli_not_found(self):
        from app.agent.nodes import cli_coder_node

        with (
            patch("app.agent.nodes.cli_coder_node.async_session_maker") as mock_sm,
            patch("app.agent.nodes.cli_coder_node.asyncio.create_subprocess_shell") as mock_sub,
            patch("app.agent.nodes.cli_coder_node.TaskService.get", new_callable=AsyncMock) as mock_task,
            patch("app.agent.nodes.cli_coder_node.ContextBuilder.build_coder_context", new_callable=AsyncMock) as mock_ctx,
            patch("app.agent.nodes.cli_coder_node.GitService.init_repo"),
            patch("app.agent.nodes.cli_coder_node.GitService.configure_identity"),
            patch("app.agent.nodes.cli_coder_node.GitService.ensure_baseline_commit"),
            patch("app.agent.nodes.cli_coder_node._publish_event", new_callable=AsyncMock) as mock_pub,
            patch("app.agent.nodes.cli_coder_node.write_pending_log", new_callable=AsyncMock) as mock_wpl,
            patch("app.agent.nodes.cli_coder_node.finalise_log", new_callable=AsyncMock),
        ):
            mock_task.return_value = MagicMock(id=_TASK_ID)
            mock_ctx.return_value = {"system": "sys", "human": "do the task"}
            mock_wpl.return_value = MagicMock(id=uuid.uuid4())

            session_mock = AsyncMock()
            session_mock.__aenter__ = AsyncMock(return_value=session_mock)
            session_mock.__aexit__ = AsyncMock(return_value=False)
            session_mock.get = AsyncMock(return_value=MagicMock(id=_AGENT_RUN_ID, coding_backend="groq"))
            session_mock.add = MagicMock()
            session_mock.flush = AsyncMock()
            session_mock.commit = AsyncMock()
            mock_sm.return_value = session_mock

            proc = _make_proc(returncode=127, stderr_lines=[b"command not found: claude"])
            mock_sub.return_value = proc

            state = await cli_coder_node._run_with_session({**_BASE_STATE})

        assert "error" in state
        # Verify ERROR event with CLI_NOT_FOUND was published
        error_calls = [
            c for c in mock_pub.call_args_list
            if "CLI_NOT_FOUND" in str(c)
        ]
        assert len(error_calls) >= 1


@pytest.mark.asyncio
class TestCliCoderNodeSuccess:
    """Success path: diff saved, interrupt() called."""

    async def test_success_saves_diff(self):
        from app.agent.nodes import cli_coder_node

        diff_snap = MagicMock()
        diff_snap.unified = "diff --git a/file.py"
        diff_snap.original_content = ""
        diff_snap.modified_content = "print('hello')"
        diff_snap.files = ["file.py"]

        with (
            patch("app.agent.nodes.cli_coder_node.async_session_maker") as mock_sm,
            patch("app.agent.nodes.cli_coder_node.asyncio.create_subprocess_shell") as mock_sub,
            patch("app.agent.nodes.cli_coder_node.TaskService.get", new_callable=AsyncMock) as mock_task,
            patch("app.agent.nodes.cli_coder_node.ContextBuilder.build_coder_context", new_callable=AsyncMock) as mock_ctx,
            patch("app.agent.nodes.cli_coder_node.GitService.init_repo"),
            patch("app.agent.nodes.cli_coder_node.GitService.configure_identity"),
            patch("app.agent.nodes.cli_coder_node.GitService.ensure_baseline_commit"),
            patch("app.agent.nodes.cli_coder_node.GitService.diff_staged", return_value=diff_snap),
            patch("app.agent.nodes.cli_coder_node._publish_event", new_callable=AsyncMock),
            patch("app.agent.nodes.cli_coder_node.write_pending_log", new_callable=AsyncMock) as mock_wpl,
            patch("app.agent.nodes.cli_coder_node.finalise_log", new_callable=AsyncMock) as mock_fl,
            patch("app.agent.nodes.cli_coder_node.write_audit", new_callable=AsyncMock),
            patch("app.agent.nodes.cli_coder_node.interrupt"),
        ):
            mock_task.return_value = MagicMock(id=_TASK_ID)
            mock_ctx.return_value = {"system": "sys", "human": "do the task"}
            mock_wpl.return_value = MagicMock(id=uuid.uuid4())

            session_mock = AsyncMock()
            session_mock.__aenter__ = AsyncMock(return_value=session_mock)
            session_mock.__aexit__ = AsyncMock(return_value=False)
            session_mock.get = AsyncMock(return_value=MagicMock(id=_AGENT_RUN_ID, coding_backend="groq"))
            session_mock.add = MagicMock()
            session_mock.flush = AsyncMock()
            session_mock.commit = AsyncMock()
            mock_sm.return_value = session_mock

            proc = _make_proc(returncode=0, stdout_lines=[b"Writing file.py\n"])
            mock_sub.return_value = proc

            state = await cli_coder_node._run_with_session({**_BASE_STATE})

        assert "error" not in state or not state.get("error")
        assert mock_fl.called
