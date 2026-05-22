"""Unit tests for token_optimizer.py (T119)."""

import pytest

from app.tools.token_optimizer import (
    compress_git_diff,
    compress_git_log,
    compress_git_status,
    deduplicate_lines,
    filter_test_output,
    group_build_errors,
    optimize_command_output,
    optimize_file_content,
    optimize_list_output,
)


# ---------------------------------------------------------------------------
# optimize_list_output
# ---------------------------------------------------------------------------

class TestOptimizeListOutput:
    def test_basic_tree(self):
        paths = ["src/models/user.py", "src/models/task.py", "tests/test_user.py"]
        result = optimize_list_output(paths)
        assert "src/" in result
        assert "models/" in result
        assert "(2 files)" in result
        assert "tests/" in result
        assert "(1 file)" in result

    def test_flat_single_file(self):
        result = optimize_list_output(["README.md"])
        assert "README.md" in result

    def test_empty_list(self):
        result = optimize_list_output([])
        assert "empty" in result.lower()

    def test_uses_directory_separator(self):
        paths = ["a/b/c.py", "a/b/d.py", "a/e.py"]
        result = optimize_list_output(paths)
        assert "/" in result

    def test_file_count_in_directory(self):
        paths = [f"src/file{i}.py" for i in range(5)]
        result = optimize_list_output(paths)
        assert "(5 files)" in result


# ---------------------------------------------------------------------------
# optimize_file_content
# ---------------------------------------------------------------------------

class TestOptimizeFileContent:
    def test_short_content_unchanged(self):
        content = "line1\nline2\nline3"
        result = optimize_file_content(content, max_lines=500)
        assert "line1" in result
        assert "line2" in result

    def test_ansi_stripped(self):
        content = "\x1b[32mgreen text\x1b[0m"
        result = optimize_file_content(content)
        assert "\x1b[" not in result
        assert "green text" in result

    def test_blank_line_collapse(self):
        content = "a\n\n\n\n\nb"
        result = optimize_file_content(content)
        assert "\n\n\n" not in result

    def test_truncation_600_lines(self):
        lines = [f"line {i}" for i in range(600)]
        content = "\n".join(lines)
        result = optimize_file_content(content, max_lines=500)
        assert "omitted" in result
        result_lines = result.splitlines()
        assert len(result_lines) <= 300

    def test_truncation_keeps_head_and_tail(self):
        lines = [f"line {i}" for i in range(600)]
        content = "\n".join(lines)
        result = optimize_file_content(content, max_lines=500)
        assert "line 0" in result
        assert "line 599" in result

    def test_empty_input(self):
        assert optimize_file_content("") == ""


# ---------------------------------------------------------------------------
# filter_test_output
# ---------------------------------------------------------------------------

class TestFilterTestOutput:
    PASSING_OUTPUT = (
        "collected 50 items\n"
        ".........................\n"
        "50 passed in 1.23s"
    )

    FAILING_OUTPUT = (
        "collected 50 items\n"
        "....FAILED tests/test_foo.py::test_bar - AssertionError: 1 != 2\n"
        "FAILED tests/test_baz.py::test_qux - TypeError: unsupported\n"
        "3 failed, 47 passed in 2.34s"
    )

    def test_passing_run_returns_only_last_line(self):
        result = filter_test_output(self.PASSING_OUTPUT)
        assert "50 passed" in result
        assert "collected" not in result

    def test_failing_run_keeps_failed_lines(self):
        result = filter_test_output(self.FAILING_OUTPUT)
        assert "FAILED" in result
        assert "AssertionError" in result

    def test_failing_run_includes_summary(self):
        result = filter_test_output(self.FAILING_OUTPUT)
        assert "3 failed" in result

    def test_empty_output(self):
        result = filter_test_output("")
        assert result  # non-empty


# ---------------------------------------------------------------------------
# compress_git_diff
# ---------------------------------------------------------------------------

class TestCompressGitDiff:
    GIT_DIFF = (
        "diff --git a/foo.py b/foo.py\n"
        "index 1234567..abcdefg 100644\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,5 +1,5 @@\n"
        " context line 1\n"
        " context line 2\n"
        "-old line\n"
        "+new line\n"
        " context line 3\n"
    )

    def test_no_space_prefix_lines(self):
        result = compress_git_diff(self.GIT_DIFF)
        for line in result.splitlines():
            assert not line.startswith(" "), f"Context line leaked: {line!r}"

    def test_keeps_added_removed(self):
        result = compress_git_diff(self.GIT_DIFF)
        assert "-old line" in result
        assert "+new line" in result

    def test_keeps_hunk_headers(self):
        result = compress_git_diff(self.GIT_DIFF)
        assert "@@" in result

    def test_keeps_file_headers(self):
        result = compress_git_diff(self.GIT_DIFF)
        assert "--- a/foo.py" in result
        assert "+++ b/foo.py" in result

    def test_empty_diff(self):
        result = compress_git_diff("")
        assert "empty" in result.lower()


# ---------------------------------------------------------------------------
# compress_git_log
# ---------------------------------------------------------------------------

class TestCompressGitLog:
    GIT_LOG = (
        "commit abc1234567890\n"
        "Author: Alice Smith <alice@example.com>\n"
        "Date:   Mon Jan 1 00:00:00 2024 +0000\n"
        "\n"
        "    Add new feature\n"
        "\n"
        "commit def9876543210\n"
        "Author: Bob Jones <bob@example.com>\n"
        "Date:   Sun Dec 31 23:59:59 2023 +0000\n"
        "\n"
        "    Fix critical bug\n"
    )

    def test_one_line_per_commit(self):
        result = compress_git_log(self.GIT_LOG)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_contains_short_hash(self):
        result = compress_git_log(self.GIT_LOG)
        assert "abc1234" in result

    def test_contains_subject(self):
        result = compress_git_log(self.GIT_LOG)
        assert "Add new feature" in result
        assert "Fix critical bug" in result

    def test_empty_log(self):
        result = compress_git_log("")
        assert "no log" in result.lower()


# ---------------------------------------------------------------------------
# compress_git_status
# ---------------------------------------------------------------------------

class TestCompressGitStatus:
    CLEAN_STATUS = "On branch main\nnothing to commit, working tree clean\n"
    DIRTY_STATUS = (
        "On branch feature/foo\n"
        "Changes not staged for commit:\n"
        "  modified:   src/app.py\n"
        "Untracked files:\n"
        "?? newfile.txt\n"
    )

    def test_clean_status(self):
        result = compress_git_status(self.CLEAN_STATUS)
        assert "nothing to commit" in result

    def test_branch_line_included(self):
        result = compress_git_status(self.DIRTY_STATUS)
        assert "feature/foo" in result

    def test_shows_counts(self):
        result = compress_git_status(self.DIRTY_STATUS)
        assert "untracked:" in result.lower()

    def test_empty_status(self):
        result = compress_git_status("")
        assert "clean" in result.lower()


# ---------------------------------------------------------------------------
# group_build_errors
# ---------------------------------------------------------------------------

class TestGroupBuildErrors:
    TS_ERRORS = (
        "src/app.ts(42,5): error TS2345 Argument of type 'string' is not assignable\n"
        "src/app.ts(67,10): error TS2304 Cannot find name 'foo'\n"
        "src/utils.ts(12,1): error TS2551 Property 'bar' does not exist\n"
    )

    def test_groups_by_file(self):
        result = group_build_errors(self.TS_ERRORS)
        assert "src/app.ts" in result
        assert "src/utils.ts" in result

    def test_shows_error_count(self):
        result = group_build_errors(self.TS_ERRORS)
        assert "(2 errors)" in result or "2 errors" in result

    def test_includes_line_number(self):
        result = group_build_errors(self.TS_ERRORS)
        assert "line 42" in result

    def test_empty_output(self):
        result = group_build_errors("")
        assert "no errors" in result.lower()


# ---------------------------------------------------------------------------
# deduplicate_lines
# ---------------------------------------------------------------------------

class TestDeduplicateLines:
    def test_collapses_repeated_lines(self):
        text = "x\nx\nx\nx\nx"
        result = deduplicate_lines(text, threshold=3)
        assert "× 5" in result
        assert result.count("x") <= 2  # compressed notation

    def test_below_threshold_unchanged(self):
        text = "a\na\nb"
        result = deduplicate_lines(text, threshold=3)
        assert result == "a\na\nb"

    def test_empty_input(self):
        assert deduplicate_lines("") == ""

    def test_mixed_content(self):
        text = "unique\nrepeat\nrepeat\nrepeat\nunique2"
        result = deduplicate_lines(text, threshold=3)
        assert "repeat × 3" in result
        assert "unique" in result
        assert "unique2" in result


# ---------------------------------------------------------------------------
# optimize_command_output (routing)
# ---------------------------------------------------------------------------

class TestOptimizeCommandOutput:
    def test_pytest_routed_to_filter(self):
        stdout = "FAILED test_foo.py::test_bar - AssertionError\n2 failed in 1s"
        result = optimize_command_output("pytest", stdout, "", 1)
        assert "exit_code: 1" in result
        assert "FAILED" in result

    def test_git_diff_routed(self):
        diff = "--- a/foo.py\n+++ b/foo.py\n @@ -1 +1 @@\n-old\n+new\n context\n"
        result = optimize_command_output("git diff", diff, "", 0)
        assert "exit_code: 0" in result
        assert "+new" in result

    def test_git_log_routed(self):
        log = (
            "commit abc1234567\nAuthor: A <a@b.com>\nDate:   Mon\n\n    msg\n"
        )
        result = optimize_command_output("git log --oneline", log, "", 0)
        assert "exit_code: 0" in result

    def test_tsc_routed_to_group(self):
        err = "src/foo.ts(1,1): error TS0001 Something wrong\n"
        result = optimize_command_output("tsc --noEmit", "", err, 1)
        assert "exit_code: 1" in result

    def test_default_returns_deduped_stdout(self):
        stdout = "same\nsame\nsame\nsame"
        result = optimize_command_output("ls -la", stdout, "", 0)
        assert "exit_code: 0" in result

    def test_always_has_exit_code_prefix(self):
        result = optimize_command_output("echo hi", "hi", "", 0)
        assert result.startswith("exit_code:")
