"""RTK-inspired token compression module for LLM agent tool outputs (T118).

Implements four RTK-AI/RTK techniques:
  - Smart Filtering  : filter_test_output, optimize_file_content
  - Grouping         : optimize_list_output, group_build_errors
  - Truncation       : optimize_file_content (head/tail)
  - Deduplication    : deduplicate_lines

All functions are pure (no I/O, no async). See research.md RTK analysis for background.
"""

from __future__ import annotations

import re
from collections import defaultdict


def optimize_list_output(paths: list[str]) -> str:
    """Convert flat file-path list → compact directory tree with file counts.

    Example:
        ["src/models/user.py", "src/models/task.py", "tests/test_user.py"]
        →
        src/
          models/ (2 files)
            user.py
            task.py
        tests/ (1 file)
          test_user.py
    """
    if not paths:
        return "(empty directory)"

    # Build nested dict tree
    tree: dict = {}
    for p in paths:
        parts = p.replace("\\", "/").split("/")
        node = tree
        for part in parts:
            node = node.setdefault(part, {})

    lines: list[str] = []

    def _render(node: dict, depth: int, prefix: str) -> None:
        dirs = {k: v for k, v in node.items() if v}
        files = [k for k, v in node.items() if not v]
        for name, child in sorted(dirs.items()):
            file_count = _count_leaves(child)
            unit = "file" if file_count == 1 else "files"
            lines.append("  " * depth + f"{prefix}{name}/ ({file_count} {unit})")
            _render(child, depth + 1, "")
        for name in sorted(files):
            lines.append("  " * depth + name)

    def _count_leaves(node: dict) -> int:
        if not node:
            return 1
        return sum(_count_leaves(v) for v in node.values())

    _render(tree, 0, "")
    return "\n".join(lines)


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[mGKHF]")


def optimize_file_content(content: str, max_lines: int = 500) -> str:
    """Smart-filter file content for LLM consumption.

    Steps (in order):
    1. Strip ANSI escape codes.
    2. Collapse runs of ≥3 blank lines to exactly 1 blank line.
    3. If line count > max_lines: keep first 100 + last 100, insert skip notice.
    """
    if not content:
        return content

    text = _ANSI_ESCAPE.sub("", content)

    # Collapse ≥3 consecutive blank lines → 1 blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text

    head = lines[:100]
    tail = lines[-100:]
    omitted = len(lines) - 200
    return "\n".join(head) + f"\n\n… {omitted} lines omitted …\n\n" + "\n".join(tail)


def optimize_command_output(cmd: str, stdout: str, stderr: str, exit_code: int) -> str:
    """Route command output through the appropriate RTK technique.

    Always prepends "exit_code: N\\n\\n". Routing order:
    pytest / python -m pytest → filter_test_output
    jest / npx jest           → filter_test_output
    cargo test / go test      → filter_test_output
    git diff                  → compress_git_diff
    git log                   → compress_git_log
    git status                → compress_git_status
    tsc / npx tsc             → group_build_errors(stderr or stdout)
    eslint / npx eslint       → group_build_errors
    ruff / flake8             → group_build_errors
    default                   → deduplicate_lines(stdout) + raw stderr
    """
    stripped_cmd = (cmd or "").strip()
    prefix = f"exit_code: {exit_code}\n\n"

    combined = (stdout or "") + "\n" + (stderr or "")

    if re.match(r"(pytest|python\s+-m\s+pytest)", stripped_cmd):
        return prefix + filter_test_output(combined)
    if re.match(r"(jest|npx\s+jest)", stripped_cmd):
        return prefix + filter_test_output(combined)
    if re.match(r"(cargo\s+test|go\s+test)", stripped_cmd):
        return prefix + filter_test_output(combined)
    if re.match(r"git\s+diff", stripped_cmd):
        return prefix + compress_git_diff(stdout or "")
    if re.match(r"git\s+log", stripped_cmd):
        return prefix + compress_git_log(stdout or "")
    if re.match(r"git\s+status", stripped_cmd):
        return prefix + compress_git_status(stdout or "")
    if re.match(r"(tsc|npx\s+tsc)", stripped_cmd):
        return prefix + group_build_errors(stderr or stdout or "")
    if re.match(r"(eslint|npx\s+eslint)", stripped_cmd):
        return prefix + group_build_errors(stdout or "")
    if re.match(r"(ruff|flake8)", stripped_cmd):
        return prefix + group_build_errors(stdout or "")

    deduped_stdout = deduplicate_lines(stdout or "")
    raw_stderr = (stderr or "").strip()
    result = deduped_stdout
    if raw_stderr:
        result += "\n\nstderr:\n" + raw_stderr
    return prefix + result


_TEST_FAILURE_PATTERNS = re.compile(
    r"FAILED|ERROR|ERRORS|AssertionError|TypeError|ImportError|PermissionError"
    r"|Exception|Traceback|× |✕ |✗ ",
)


def filter_test_output(output: str) -> str:
    """Keep only FAILED/ERROR lines + final summary line.

    If no failures found, returns last non-empty line only (all-pass summary).
    """
    if not output:
        return "(no output)"

    lines = output.splitlines()
    kept: list[str] = []
    in_traceback = False

    for line in lines:
        if "Traceback" in line:
            in_traceback = True
        if in_traceback:
            kept.append(line)
            if line.strip() and not line.startswith(" ") and "Traceback" not in line and len(kept) > 1:
                in_traceback = False
            continue
        if _TEST_FAILURE_PATTERNS.search(line):
            kept.append(line)

    # Always include last non-empty line (summary)
    last_line = next((l for l in reversed(lines) if l.strip()), "")
    if last_line and (not kept or kept[-1] != last_line):
        kept.append(last_line)

    if not kept:
        return last_line or output.strip()

    return "\n".join(kept)


def compress_git_diff(diff: str) -> str:
    """Retain only file headers (---/+++) and changed lines (+/-/@@ hunk headers).

    Strips context lines (space-prefix) to reduce ~70% of diff tokens.
    """
    if not diff:
        return "(empty diff)"

    kept = []
    for line in diff.splitlines():
        if line.startswith((" ",)):
            continue
        kept.append(line)
    return "\n".join(kept) if kept else "(empty diff)"


def compress_git_log(log: str) -> str:
    """Summarise git log to one line per commit: hash(7) · author · date · subject."""
    if not log:
        return "(no log)"

    lines = []
    current: dict[str, str] = {}

    def _flush() -> None:
        if current:
            hash_ = current.get("commit", "")[:7]
            author = current.get("Author", "").split("<")[0].strip()
            date = current.get("Date", "").strip()
            subject = current.get("subject", "").strip()
            lines.append(f"{hash_} · {author} · {date} · {subject}")

    for raw in log.splitlines():
        if raw.startswith("commit "):
            _flush()
            current = {"commit": raw[7:].strip(), "subject": ""}
        elif raw.startswith("Author:"):
            current["Author"] = raw[7:].strip()
        elif raw.startswith("Date:"):
            current["Date"] = raw[5:].strip()
        elif raw.strip() and current.get("subject") == "":
            current["subject"] = raw.strip()

    _flush()
    return "\n".join(lines) if lines else log.strip()


def compress_git_status(status: str) -> str:
    """Compact git status: branch line + counts of staged/unstaged/untracked."""
    if not status:
        return "(clean)"

    branch_line = ""
    staged = 0
    unstaged = 0
    untracked = 0

    for line in status.splitlines():
        if line.startswith("On branch") or line.startswith("HEAD detached"):
            branch_line = line.strip()
        elif line.startswith("Changes to be committed"):
            staged_block = True
        elif line.startswith("Changes not staged"):
            staged_block = False
        elif line.startswith("\t") or line.startswith("  "):
            stripped = line.strip()
            if stripped.startswith("??") or stripped.startswith("?"):
                untracked += 1
            elif "staged" in status[: status.find(line)] if line in status else False:
                staged += 1
            else:
                unstaged += 1
        elif line.startswith("??"):
            untracked += 1

    # Simpler re-parse for accuracy
    staged = len(re.findall(r"^[MADRC]\s", status, re.MULTILINE))
    unstaged = len(re.findall(r"^.[MADRC\?]\s", status, re.MULTILINE))
    untracked_lines = re.findall(r"^\?\?", status, re.MULTILINE)
    untracked = len(untracked_lines)

    parts = []
    if branch_line:
        parts.append(branch_line)
    parts.append(f"staged: {staged}, unstaged: {unstaged}, untracked: {untracked}")

    nothing_msg = re.search(r"nothing to commit", status)
    if nothing_msg:
        parts.append("nothing to commit, working tree clean")

    return "\n".join(parts)


def group_build_errors(output: str) -> str:
    """Group compiler/linter errors by file path.

    Format:
        path/to/file.ts (3 errors)
          line 42: TS2345 Argument of type ...
          line 67: TS2304 Cannot find name ...
    """
    if not output:
        return "(no errors)"

    # Pattern: path/to/file.ext(line,col): error message  [TypeScript / ESLint style]
    ts_pattern = re.compile(r"^(.+?)\((\d+),\d+\):\s*(?:error|warning)\s+(.+)$", re.MULTILINE)
    # Pattern: path/to/file.ext:line:col: message  [ruff/flake8 style]
    py_pattern = re.compile(r"^(.+?):(\d+):\d+:\s+(.+)$", re.MULTILINE)
    # ESLint: path/to/file line N: message
    eslint_pattern = re.compile(r"^\s+(\d+):\d+\s+(?:error|warning)\s+(.+)$", re.MULTILINE)

    grouped: dict[str, list[str]] = defaultdict(list)

    # Try TypeScript style first
    ts_matches = ts_pattern.findall(output)
    if ts_matches:
        for file_path, line_no, msg in ts_matches:
            grouped[file_path.strip()].append(f"  line {line_no}: {msg.strip()}")
    else:
        py_matches = py_pattern.findall(output)
        for file_path, line_no, msg in py_matches:
            grouped[file_path.strip()].append(f"  line {line_no}: {msg.strip()}")

    if not grouped:
        # Fall back: return deduped output
        return deduplicate_lines(output)

    lines = []
    for file_path, errors in sorted(grouped.items()):
        count = len(errors)
        unit = "error" if count == 1 else "errors"
        lines.append(f"{file_path} ({count} {unit})")
        lines.extend(errors)
    return "\n".join(lines)


def deduplicate_lines(text: str, threshold: int = 3) -> str:
    """Collapse consecutive identical lines (≥ threshold) into 'line × N' notation."""
    if not text:
        return text

    lines = text.splitlines()
    if not lines:
        return text

    result: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i]
        j = i + 1
        while j < len(lines) and lines[j] == current:
            j += 1
        count = j - i
        if count >= threshold:
            result.append(f"{current} × {count}")
        else:
            result.extend(lines[i:j])
        i = j

    return "\n".join(result)
