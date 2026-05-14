"""Unit tests for ``codebase_mapper`` (US14 / T098)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.codebase_mapper import build_codebase_map_dict


def test_build_python_map_extracts_class_function_and_method(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text(
        '"""module docstring"""\n\n'
        'class Foo:\n'
        '    """class doc"""\n'
        "    def bar(self, x: int) -> None:\n"
        "        pass\n\n"
        "def spam(a: str) -> int:\n"
        "    return 1\n",
        encoding="utf-8",
    )
    pid = uuid4()
    m, n = build_codebase_map_dict(pid, tmp_path, "python")
    assert n == 1
    assert m["file_count"] == 1
    assert m["language"] == "python"
    assert m["project_id"] == str(pid)
    f0 = m["files"][0]
    assert f0["path"].endswith("pkg/mod.py")
    kinds = {(s["type"], s["name"]) for s in f0["symbols"]}
    assert ("class", "Foo") in kinds
    assert ("function", "spam") in kinds
    foo = next(s for s in f0["symbols"] if s["name"] == "Foo")
    assert foo["type"] == "class"
    assert any(ch.get("name") == "bar" for ch in foo.get("children", []))


def test_directory_tree_contains_scanned_file(tmp_path):
    (tmp_path / "a.py").write_text("# noop\n", encoding="utf-8")
    m, _ = build_codebase_map_dict(uuid4(), tmp_path, "python")
    tree = m["directory_tree"]
    assert tree["type"] == "directory"
    names = {c["name"] for c in tree.get("children", [])}
    assert "a.py" in names


def test_javascript_export_class_and_function(tmp_path):
    (tmp_path / "app.js").write_text(
        "export class X {\n  m() {}\n}\nexport function f() { return 1; }\n",
        encoding="utf-8",
    )
    m, n = build_codebase_map_dict(uuid4(), tmp_path, "javascript")
    assert n == 1
    syms = m["files"][0]["symbols"]
    kinds = {(s["type"], s["name"]) for s in syms}
    assert ("class", "X") in kinds
    assert ("function", "f") in kinds


def test_invalid_language_raises(tmp_path):
    with pytest.raises(ValueError, match="language must be one of"):
        build_codebase_map_dict(uuid4(), tmp_path, "rust")
