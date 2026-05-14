"""Tree-sitter codebase structure map (US14 / T098).

Builds ``CodebaseMap`` JSON per ``specs/001-neo-kanban/plan.md`` § Codebase Map JSON Schema,
persists a row in ``codebase_maps``, and returns the same payload.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.codebase_map import CodebaseMap

logger = logging.getLogger(__name__)

ScanLanguage = Literal["python", "javascript", "typescript"]

_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        ".eggs",
        "htmlcov",
        ".idea",
        ".vscode",
    }
)

_MAX_READ_BYTES = 400_000


class _DirNode:
    __slots__ = ("name", "dirs", "files")

    def __init__(self, name: str) -> None:
        self.name = name
        self.dirs: dict[str, _DirNode] = {}
        self.files: list[str] = []

    def to_json(self) -> dict[str, Any]:
        dir_children = sorted(self.dirs.values(), key=lambda n: n.name.lower())
        children: list[dict[str, Any]] = [d.to_json() for d in dir_children]
        children.extend({"name": fn, "type": "file"} for fn in sorted(self.files, key=str.lower))
        return {"name": self.name, "type": "directory", "children": children}


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=1)
def _parser_python():
    from tree_sitter import Language, Parser

    import tree_sitter_python as tsp

    return Parser(Language(tsp.language()))


@lru_cache(maxsize=1)
def _parser_javascript():
    from tree_sitter import Language, Parser

    import tree_sitter_javascript as tsj

    return Parser(Language(tsj.language()))


@lru_cache(maxsize=1)
def _parser_typescript():
    from tree_sitter import Language, Parser

    import tree_sitter_typescript as tst

    return Parser(Language(tst.language_typescript()))


@lru_cache(maxsize=1)
def _parser_tsx():
    from tree_sitter import Language, Parser

    import tree_sitter_typescript as tst

    return Parser(Language(tst.language_tsx()))


def _extensions_for_scan_language(lang: ScanLanguage) -> frozenset[str]:
    if lang == "python":
        return frozenset({".py"})
    if lang == "javascript":
        return frozenset({".js", ".mjs", ".cjs", ".jsx"})
    return frozenset({".ts", ".tsx"})


def _parser_for_path(path: Path, scan_lang: ScanLanguage):
    suf = path.suffix.lower()
    if scan_lang == "python":
        return _parser_python()
    if scan_lang == "javascript":
        return _parser_javascript()
    if suf == ".tsx":
        return _parser_tsx()
    return _parser_typescript()


def _file_language_label(path: Path) -> str:
    m = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }
    return m.get(path.suffix.lower(), "unknown")


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _rel_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _iter_source_files(root: Path, scan_lang: ScanLanguage):
    root = root.resolve()
    exts = _extensions_for_scan_language(scan_lang)
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dp = Path(dirpath)
        # prune skip dirs
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIP_DIR_NAMES
            and not d.startswith(".")
            and not d.endswith(".egg-info")
        ]
        for fn in filenames:
            p = dp / fn
            if p.suffix.lower() not in exts:
                continue
            if p.name.startswith("."):
                continue
            try:
                if p.is_symlink():
                    continue
            except OSError:
                continue
            yield p


def _insert_path(tree_root: _DirNode, rel: str) -> None:
    parts = Path(rel).parts
    if not parts:
        return
    cur = tree_root
    for seg in parts[:-1]:
        cur = cur.dirs.setdefault(seg, _DirNode(seg))
    cur.files.append(parts[-1])


def _build_directory_tree(root: Path, rel_files: list[str]) -> dict[str, Any]:
    name = root.name or root.resolve().as_posix().rstrip("/").split("/")[-1] or "."
    tree = _DirNode(name)
    for rf in rel_files:
        _insert_path(tree, rf)
    return tree.to_json()


def _py_signature(node, source: bytes) -> str:
    params = node.child_by_field_name("parameters")
    if params is None:
        return " ".join(_node_text(source, node).split())[:2000]
    ret = node.child_by_field_name("return_type")
    end = ret.end_byte if ret is not None else params.end_byte
    frag = source[node.start_byte : end].decode("utf-8", errors="replace").strip()
    return " ".join(frag.split())[:2000]


def _py_name(node, source: bytes) -> str:
    n = node.child_by_field_name("name")
    if n is None:
        return "?"
    return _node_text(source, n).strip()


def _py_docstring(block_node, source: bytes) -> str | None:
    body = block_node.child_by_field_name("body")
    if body is None or not body.named_children:
        return None
    first = body.named_children[0]
    if first.type != "expression_statement":
        return None
    for ch in first.named_children:
        if ch.type == "string":
            raw = _node_text(source, ch).strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
                inner = raw[1:-1]
                if inner.startswith(("'", '"')) and inner.endswith(("'", '"')) and len(inner) >= 2:
                    inner = inner[1:-1]
                return inner.strip()[:5000] or None
    return None


def _py_method(node, source: bytes) -> dict[str, Any]:
    return {
        "type": "method",
        "name": _py_name(node, source),
        "signature": _py_signature(node, source),
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
    }


def _py_class(node, source: bytes) -> dict[str, Any]:
    body = node.child_by_field_name("body")
    methods: list[dict[str, Any]] = []
    if body is not None:
        for st in body.named_children:
            if st.type == "function_definition":
                methods.append(_py_method(st, source))
    return {
        "type": "class",
        "name": _py_name(node, source),
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "docstring": _py_docstring(node, source),
        "children": methods,
    }


def _py_function(node, source: bytes) -> dict[str, Any]:
    return {
        "type": "function",
        "name": _py_name(node, source),
        "signature": _py_signature(node, source),
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
    }


def _py_iter_top_level(root_node):
    for ch in root_node.named_children:
        if ch.type == "decorated_definition":
            defn = ch.child_by_field_name("definition")
            if defn is None:
                for c in ch.named_children:
                    if c.type in ("class_definition", "function_definition"):
                        defn = c
                        break
            if defn is not None:
                yield defn
        elif ch.type in ("class_definition", "function_definition"):
            yield ch


def _extract_python_symbols(source: bytes) -> list[dict[str, Any]]:
    parser = _parser_python()
    tree = parser.parse(source)
    out: list[dict[str, Any]] = []
    for node in _py_iter_top_level(tree.root_node):
        try:
            if node.type == "class_definition":
                out.append(_py_class(node, source))
            elif node.type == "function_definition":
                out.append(_py_function(node, source))
        except Exception:
            logger.warning("python symbol extract failed for node type=%s", node.type, exc_info=True)
    return out


def _js_name(node, source: bytes) -> str:
    n = node.child_by_field_name("name")
    if n is None:
        return "?"
    return _node_text(source, n).strip()


def _js_signature(node, source: bytes) -> str:
    # Prefer header up through parameters / type annotation end.
    params = node.child_by_field_name("parameters")
    if params is None:
        return " ".join(_node_text(source, node).split())[:2000]
    ret = node.child_by_field_name("return_type")
    end = ret.end_byte if ret is not None else params.end_byte
    frag = source[node.start_byte : end].decode("utf-8", errors="replace").strip()
    return " ".join(frag.split())[:2000]


def _js_function(node, source: bytes, *, kind: str) -> dict[str, Any]:
    return {
        "type": kind,
        "name": _js_name(node, source),
        "signature": _js_signature(node, source),
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
    }


def _js_class(node, source: bytes) -> dict[str, Any]:
    body = node.child_by_field_name("body")
    methods: list[dict[str, Any]] = []
    if body is not None:
        for st in body.named_children:
            if st.type == "method_definition":
                methods.append(
                    {
                        "type": "method",
                        "name": _js_name(st, source),
                        "signature": _js_signature(st, source),
                        "start_line": st.start_point[0] + 1,
                        "end_line": st.end_point[0] + 1,
                    }
                )
    return {
        "type": "class",
        "name": _js_name(node, source),
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "docstring": None,
        "children": methods,
    }


def _js_from_lexical(node, source: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for decl in node.named_children:
        if decl.type != "variable_declarator":
            continue
        name = decl.child_by_field_name("name")
        val = decl.child_by_field_name("value")
        if name is None or val is None:
            continue
        if val.type not in ("arrow_function", "function_expression"):
            continue
        nm = _node_text(source, name).strip()
        sig = " ".join(_node_text(source, val).split())[:2000]
        out.append(
            {
                "type": "function",
                "name": nm,
                "signature": sig,
                "start_line": decl.start_point[0] + 1,
                "end_line": decl.end_point[0] + 1,
            }
        )
    return out


def _js_walk_statement(stmt, source: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if stmt.type == "function_declaration":
        out.append(_js_function(stmt, source, kind="function"))
    elif stmt.type == "class_declaration":
        out.append(_js_class(stmt, source))
    elif stmt.type == "lexical_declaration":
        out.extend(_js_from_lexical(stmt, source))
    elif stmt.type == "export_statement":
        for ch in stmt.named_children:
            out.extend(_js_walk_statement(ch, source))
    return out


def _extract_js_like_symbols(source: bytes, scan_lang: ScanLanguage, path: Path) -> list[dict[str, Any]]:
    parser = _parser_for_path(path, scan_lang)
    tree = parser.parse(source)
    out: list[dict[str, Any]] = []
    for ch in tree.root_node.named_children:
        try:
            out.extend(_js_walk_statement(ch, source))
        except Exception:
            logger.warning("js/ts symbol extract failed stmt type=%s", ch.type, exc_info=True)
    return out


def _extract_symbols(path: Path, source: bytes, scan_lang: ScanLanguage) -> list[dict[str, Any]]:
    if scan_lang == "python":
        return _extract_python_symbols(source)
    return _extract_js_like_symbols(source, scan_lang, path)


def build_codebase_map_dict(
    project_id: UUID,
    project_root: Path,
    language: str,
) -> tuple[dict[str, Any], int]:
    """Scan ``project_root`` and return ``(map_json, file_count)`` without touching the DB."""
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"project_root is not a directory: {root}")
    lang_l = language.lower()
    if lang_l not in ("python", "javascript", "typescript"):
        raise ValueError("language must be one of: python, javascript, typescript")
    scan_lang: ScanLanguage = lang_l  # type: ignore[assignment]

    files_payload: list[dict[str, Any]] = []
    rel_paths: list[str] = []

    for path in sorted(_iter_source_files(root, scan_lang), key=lambda p: str(p).lower()):
        rel = _rel_posix(root, path)
        rel_paths.append(rel)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        try:
            raw = path.read_bytes()
        except OSError as exc:
            logger.warning("skip unreadable file %s: %s", rel, exc)
            continue
        if len(raw) > _MAX_READ_BYTES:
            logger.warning("skip oversized file for parse (%s bytes): %s", len(raw), rel)
            files_payload.append(
                {
                    "path": rel,
                    "language": _file_language_label(path),
                    "size_bytes": size,
                    "symbols": [],
                }
            )
            continue
        try:
            symbols = _extract_symbols(path, raw, scan_lang)
        except Exception:
            logger.warning("tree-sitter parse failed for %s", rel, exc_info=True)
            symbols = []
        files_payload.append(
            {
                "path": rel,
                "language": _file_language_label(path),
                "size_bytes": size,
                "symbols": symbols,
            }
        )

    file_count = len(files_payload)
    map_json: dict[str, Any] = {
        "project_id": str(project_id),
        "generated_at": _now_iso_z(),
        "language": lang_l,
        "root_path": str(root),
        "file_count": file_count,
        "directory_tree": _build_directory_tree(root, rel_paths),
        "files": sorted(files_payload, key=lambda f: f["path"].lower()),
    }
    return map_json, file_count


class CodebaseMapperService:
    """Persists a ``CodebaseMap`` row and returns ``map_json``."""

    @staticmethod
    async def scan_and_store(
        session: AsyncSession,
        *,
        project_id: UUID,
        project_root: Path,
        language: str,
        task_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Build map JSON, insert ``codebase_maps`` row, ``flush``. Caller should ``commit``."""
        map_json, file_count = build_codebase_map_dict(project_id, project_root, language)
        row = CodebaseMap(
            project_id=project_id,
            task_id=task_id,
            map_json=map_json,
            language=language.lower(),
            file_count=file_count,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return map_json
