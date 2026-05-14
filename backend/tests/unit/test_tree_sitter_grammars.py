"""Isolation smoke tests for tree-sitter grammar bindings (US14 / T101).

Loads each pinned grammar, builds a ``Parser``, parses a minimal snippet.
Run without app conftest: ``pytest tests/unit/test_tree_sitter_grammars.py --noconftest``.
"""

from __future__ import annotations

from tree_sitter import Language, Parser


def test_python_grammar_loads_and_parses() -> None:
    import tree_sitter_python as tsp

    parser = Parser(Language(tsp.language()))
    tree = parser.parse(b"def hello():\n    pass\n")
    assert tree.root_node.type == "module"


def test_javascript_grammar_loads_and_parses() -> None:
    import tree_sitter_javascript as tsj

    parser = Parser(Language(tsj.language()))
    tree = parser.parse(b"function f() { return 1; }\n")
    assert tree.root_node.type == "program"


def test_typescript_grammar_loads_and_parses() -> None:
    import tree_sitter_typescript as tst

    parser = Parser(Language(tst.language_typescript()))
    tree = parser.parse(b"const x: number = 1;\n")
    assert tree.root_node.type == "program"


def test_tsx_grammar_loads_and_parses() -> None:
    import tree_sitter_typescript as tst

    parser = Parser(Language(tst.language_tsx()))
    tree = parser.parse(b"const el = <div />;\n")
    assert tree.root_node.type == "program"
