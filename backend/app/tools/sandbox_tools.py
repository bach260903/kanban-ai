"""Sandbox command execution LangChain tool (T034)."""

from __future__ import annotations

import asyncio
from uuid import UUID

from langchain_core.tools import StructuredTool

from app.tools.file_tools import _project_root


async def run_command(project_id: UUID | str, cmd: str) -> str:
    """Run ``cmd`` in a subprocess shell with cwd = project sandbox; 60s timeout.

    Captures stdout and stderr (UTF-8 with replacement on decode errors).
    """
    root = _project_root(project_id)
    root.mkdir(parents=True, exist_ok=True)
    stripped = (cmd or "").strip()
    if not stripped:
        return "error: empty command"

    proc = await asyncio.create_subprocess_shell(
        stripped,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(root),
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=60.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return "error: command exceeded 60 second limit"

    stdout = (stdout_b or b"").decode("utf-8", errors="replace")
    stderr = (stderr_b or b"").decode("utf-8", errors="replace")
    code = proc.returncode if proc.returncode is not None else -1
    return f"exit_code: {code}\n\nstdout:\n{stdout}\n\nstderr:\n{stderr}"


def build_sandbox_tools(project_id: UUID | str) -> list[StructuredTool]:
    """Create project-scoped LangChain tools for sandbox shell execution."""
    pid = str(project_id)

    async def _run(cmd: str) -> str:
        return await run_command(pid, cmd)

    return [
        StructuredTool.from_function(
            coroutine=_run,
            name="run_command",
            description=(
                "Run a shell command with working directory set to the project sandbox root. "
                "Stdout and stderr are captured. Hard limit 60 seconds per invocation."
            ),
        ),
    ]
