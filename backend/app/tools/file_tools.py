"""Sandbox-aware file tools for LangChain agents (T033)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from langchain_core.tools import StructuredTool

from app.config import settings
from app.exceptions import SandboxEscapeError


def _project_root(project_id: UUID | str) -> Path:
    return (Path(settings.sandbox_root) / str(project_id)).resolve()


def _resolve_in_project(project_id: UUID | str, target: str | Path) -> Path:
    root = _project_root(project_id)
    candidate = (root / target).resolve()
    if candidate != root and root not in candidate.parents:
        raise SandboxEscapeError("Path escapes project sandbox root.")
    return candidate


def read_file(project_id: UUID | str, path: str) -> str:
    file_path = _resolve_in_project(project_id, path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return file_path.read_text(encoding="utf-8")


def write_file(project_id: UUID | str, path: str, content: str) -> str:
    file_path = _resolve_in_project(project_id, path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)


def list_files(project_id: UUID | str, directory: str = ".") -> list[str]:
    base_dir = _resolve_in_project(project_id, directory)
    if not base_dir.exists() or not base_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")
    root = _project_root(project_id)
    return sorted(
        str(path.relative_to(root))
        for path in base_dir.rglob("*")
        if path.is_file()
    )


def build_file_tools(project_id: UUID | str) -> list[StructuredTool]:
    """Create project-scoped LangChain `Tool` wrappers."""
    pid = str(project_id)
    def _read(path: str) -> str:
        return read_file(pid, path)

    def _write(path: str, content: str) -> str:
        return write_file(pid, path, content)

    def _list(directory: str = ".") -> list[str]:
        return list_files(pid, directory)

    return [
        StructuredTool.from_function(
            func=_read,
            name="read_file",
            description="Read UTF-8 text file inside current project sandbox.",
        ),
        StructuredTool.from_function(
            func=_write,
            name="write_file",
            description="Write UTF-8 text content to a file inside project sandbox.",
        ),
        StructuredTool.from_function(
            func=_list,
            name="list_files",
            description="List all files under a directory inside project sandbox.",
        ),
    ]
