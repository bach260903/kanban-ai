# TC-11 — Codebase map scan time (500 Python files, ≤ 10 s)

**Spec Kit:** T115  
**Related:** `tasks.md` (Phase 20 / US14), `backend/app/services/codebase_mapper.py`

## Criterion

Building a codebase map for a **synthetic project of 500** Python source files via `build_codebase_map_dict` must complete within **10 seconds** (wall clock on representative dev/CI hardware).

## Automated benchmark

```bash
cd backend && pytest tests/unit/test_codebase_mapper.py::test_tc11_500_python_files_map_within_ten_seconds -v
```

Requires the **tree-sitter** stack from `requirements.txt` (`tree-sitter`, `tree-sitter-python`, …). If `import tree_sitter` fails, the test is **skipped** (install deps in the same Python used for pytest).

Each file is a small module (`def fn(): pass`) so the benchmark stresses **walk + parse + symbol extraction**, not disk size.

## Implementation notes (T115)

- **Logging:** repeated tree-sitter failures during one scan log the first failure at `WARNING` with traceback; further failures use `DEBUG` only (avoids huge logs on 500-file runs when grammar/bindings are broken).
- **Optimisation:** if the benchmark fails on CI, profile `build_codebase_map_dict` (parse vs I/O); next steps could include batching or parallelism only if thread/process safety of parsers is verified.

## Recorded result (fill when you run the benchmark)

| Date | Machine / CI | `pytest` result | Wall time (s) | Pass (≤ 10) |
|------|----------------|-----------------|---------------|-------------|
|      |                |                 |               |             |
