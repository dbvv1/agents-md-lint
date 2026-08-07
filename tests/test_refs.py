"""Reference extraction.

Most of these are false-positive tests. A linter that flags prose gets
uninstalled after one run, so the cases it must stay quiet about matter more
than the cases it must catch.
"""

from __future__ import annotations

from contextlint.refs import RefKind, extract, extract_commands, extract_paths


def values(text: str, kind: RefKind) -> list[str]:
    return [r.value for r in extract(text) if r.kind is kind]


class TestPathExtraction:
    def test_backticked_path_with_separator(self):
        assert values("see `src/main.py` for details", RefKind.PATH) == ["src/main.py"]

    def test_backticked_file_with_extension(self):
        assert values("edit `pyproject.toml`", RefKind.PATH) == ["pyproject.toml"]

    def test_trailing_slash_is_preserved(self):
        """The slash is load-bearing: "`console/`" claims a directory exists,
        while a bare "`AGENTS.md`" usually just names a concept. check.py
        needs to tell those apart."""
        assert values("- `src/api/` — the API", RefKind.PATH) == ["src/api/"]

    def test_multiple_paths_on_one_line(self):
        got = values("`a/b.py` and `c/d.py`", RefKind.PATH)
        assert got == ["a/b.py", "c/d.py"]


class TestPathFalsePositives:
    """Things that look like paths and are not claims about this repo."""

    def test_bare_word_is_not_a_path(self):
        # `pytest` is a command or prose, not a file. Treating bare words as
        # paths was the largest source of noise.
        assert values("run `pytest` to test", RefKind.PATH) == []

    def test_urls_are_not_paths(self):
        assert values("see `https://example.com/a/b`", RefKind.PATH) == []

    def test_system_paths_are_not_repo_paths(self):
        assert values("binary at `/usr/local/bin/tool`", RefKind.PATH) == []

    def test_home_relative_is_ignored(self):
        assert values("config in `~/.config/app.toml`", RefKind.PATH) == []

    def test_globs_are_ignored(self):
        # A glob does not name one path, so "does it exist" is not answerable.
        assert values("all `src/**/*.py` files", RefKind.PATH) == []

    def test_placeholders_are_ignored(self):
        assert values("run in `<your-repo>`", RefKind.PATH) == []

    def test_shell_variables_are_ignored(self):
        assert values("set `$HOME/bin`", RefKind.PATH) == []

    def test_prose_in_backticks_is_not_a_path(self):
        assert values("the `agent workflow` is key", RefKind.PATH) == []

    def test_unquoted_filename_is_ignored(self):
        # Too ambiguous to check: prose mentions filenames constantly.
        assert values("edit the main.py file", RefKind.PATH) == []


class TestCommandExtraction:
    def test_command_in_bash_fence(self):
        text = "```bash\npytest -q\n```"
        assert values(text, RefKind.COMMAND) == ["pytest"]

    def test_prompt_prefix_is_stripped(self):
        text = "```sh\n$ ruff check .\n```"
        assert values(text, RefKind.COMMAND) == ["ruff"]

    def test_first_word_of_a_pipeline(self):
        text = "```bash\ncat file | grep x\n```"
        assert values(text, RefKind.COMMAND) == ["cat"]

    def test_env_prefix_is_skipped(self):
        text = "```bash\nDEBUG=1 pytest\n```"
        assert values(text, RefKind.COMMAND) == ["pytest"]


class TestCommandFalsePositives:
    def test_python_fence_is_not_commands(self):
        # A ```python block is code to read, not commands to run.
        text = "```python\nimport os\nos.getcwd()\n```"
        assert values(text, RefKind.COMMAND) == []

    def test_comments_are_skipped(self):
        text = "```bash\n# install first\npytest\n```"
        assert values(text, RefKind.COMMAND) == ["pytest"]

    def test_network_commands_are_not_checked(self):
        # Whether `curl` resolves says nothing about repo health.
        text = "```bash\ncurl https://example.com\n```"
        assert values(text, RefKind.COMMAND) == []

    def test_backticks_outside_a_fence_are_not_commands(self):
        assert extract_commands("run `pytest` now") == []

    def test_empty_fence_is_harmless(self):
        assert extract_commands("```\n```") == []


class TestLineNumbers:
    def test_line_numbers_are_one_based(self):
        text = "first line\nsecond has `src/x.py`"
        refs = extract_paths(text)
        assert refs[0].line_no == 2

    def test_context_line_is_captured(self):
        refs = extract_paths("- `src/x.py` — the thing")
        assert "the thing" in refs[0].line


class TestOrdering:
    def test_refs_are_in_line_order(self):
        text = "`a/b.py`\n\n```bash\npytest\n```\n\n`c/d.py`"
        lines = [r.line_no for r in extract(text)]
        assert lines == sorted(lines)
