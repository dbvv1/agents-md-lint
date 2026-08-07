"""Checking references against a real repo on disk."""

from __future__ import annotations

import subprocess

import pytest

from contextlint.check import check_file, find_context_files, find_repo_root


@pytest.fixture
def repo(tmp_path):
    """A git repo with a couple of real files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# guide\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def write_context(repo, body: str):
    path = repo / "CLAUDE.md"
    path.write_text(body)
    return path


class TestPathChecks:
    def test_existing_path_is_clean(self, repo):
        report = check_file(write_context(repo, "see `src/main.py`"), repo)
        assert report.ok
        assert report.checked == 1

    def test_missing_path_is_reported(self, repo):
        report = check_file(write_context(repo, "see `src/gone.py`"), repo)
        assert not report.ok
        assert report.findings[0].ref.value == "src/gone.py"

    def test_existing_directory_is_clean(self, repo):
        assert check_file(write_context(repo, "code in `src/`"), repo).ok

    def test_missing_directory_is_reported(self, repo):
        """A trailing slash is an explicit claim that a directory exists.
        This is the real voiceloop drift: CLAUDE.md listed `console/` long
        after the directory was gone."""
        report = check_file(write_context(repo, "code in `console/`"), repo)
        assert [f.ref.value for f in report.findings] == ["console/"]

    def test_paths_outside_the_repo_are_ignored(self, repo):
        # A context file may legitimately mention a sibling project.
        assert check_file(write_context(repo, "see `../other/x.py`"), repo).ok


class TestSuggestions:
    def test_moved_file_is_suggested(self, repo):
        """The common drift is a move, not a delete. Naming the new location
        is the difference between a report someone acts on and one they
        ignore."""
        report = check_file(write_context(repo, "entry at `main.py`"), repo)
        assert report.findings[0].suggestion == "src/main.py"

    def test_no_suggestion_when_nothing_matches(self, repo):
        report = check_file(write_context(repo, "see `src/nothing.py`"), repo)
        assert report.findings[0].suggestion is None

    def test_ambiguous_matches_are_all_listed(self, tmp_path):
        for d in ("a", "b"):
            (tmp_path / d).mkdir()
            (tmp_path / d / "util.py").write_text("")
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
            cwd=tmp_path,
            check=True,
        )
        report = check_file(write_context(tmp_path, "see `util.py`"), tmp_path)
        assert "a/util.py" in report.findings[0].suggestion


class TestCommandChecks:
    def test_resolvable_command_is_clean(self, repo):
        assert check_file(write_context(repo, "```bash\nls\n```"), repo).ok

    def test_missing_command_is_reported(self, repo):
        body = "```bash\ndefinitely-not-a-real-binary-xyz\n```"
        report = check_file(write_context(repo, body), repo)
        assert report.findings[0].reason == "command not found on PATH"

    def test_repo_local_script_that_exists(self, repo):
        (repo / "run.sh").write_text("#!/bin/sh\n")
        assert check_file(write_context(repo, "```bash\n./run.sh\n```"), repo).ok

    def test_repo_local_script_that_is_missing(self, repo):
        report = check_file(write_context(repo, "```bash\n./gone.sh\n```"), repo)
        assert report.findings[0].reason == "script not found"


class TestNonGitRepos:
    def test_works_without_git(self, tmp_path):
        """Not every directory is a git repo; the tool must still run."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "real.py").write_text("")
        path = tmp_path / "CLAUDE.md"
        path.write_text("`src/real.py` and `src/fake.py`")
        report = check_file(path, tmp_path)
        assert [f.ref.value for f in report.findings] == ["src/fake.py"]


class TestDiscovery:
    def test_finds_context_files(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "AGENTS.md").write_text("")
        names = {p.name for p in find_context_files(tmp_path)}
        assert names == {"CLAUDE.md", "AGENTS.md"}

    def test_skips_vendored_directories(self, tmp_path):
        """node_modules is full of other people's context files."""
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "CLAUDE.md").write_text("")
        (tmp_path / "CLAUDE.md").write_text("")
        assert len(find_context_files(tmp_path)) == 1

    def test_repo_root_detection(self, repo):
        nested = repo / "src"
        assert find_repo_root(nested) == repo


class TestReport:
    def test_clean_report_says_so(self, repo):
        assert "all resolve" in check_file(write_context(repo, "`src/main.py`"), repo).format()

    def test_broken_report_names_the_line(self, repo):
        report = check_file(write_context(repo, "line one\nsee `src/gone.py`"), repo)
        assert ":2" in report.format()


class TestSelfReferenceFalsePositives:
    """Cases found by running contextlint on its own CLAUDE.md.

    Both are guaranteed false positives on any tool that documents itself, and
    a linter that fires on its own README will not survive first contact.
    """

    def test_project_own_cli_is_not_missing(self, tmp_path):
        """A project's own entry point is rarely on PATH in development."""
        (tmp_path / "pyproject.toml").write_text('[project.scripts]\nmytool = "mytool.cli:main"\n')
        path = tmp_path / "CLAUDE.md"
        path.write_text("```bash\nmytool check\n```")
        assert check_file(path, tmp_path).ok

    def test_unknown_command_is_still_reported(self, tmp_path):
        """The self-reference exemption must not swallow real breakage."""
        (tmp_path / "pyproject.toml").write_text('[project.scripts]\nmytool = "x:main"\n')
        path = tmp_path / "CLAUDE.md"
        path.write_text("```bash\nnot-a-real-binary-abc\n```")
        assert not check_file(path, tmp_path).ok

    def test_bare_filename_as_a_concept_is_ignored(self, tmp_path):
        """ "agents read CLAUDE.md and AGENTS.md" is not a claim that both
        files exist in this repo."""
        path = tmp_path / "CLAUDE.md"
        path.write_text("agents read `CLAUDE.md` and `AGENTS.md`")
        assert check_file(path, tmp_path).ok

    def test_bare_filename_that_moved_is_reported(self, repo):
        """But when a file of that name does exist elsewhere, it is a real
        reference to a moved file and worth reporting."""
        report = check_file(write_context(repo, "entry at `main.py`"), repo)
        assert not report.ok
        assert report.findings[0].suggestion == "src/main.py"

    def test_path_with_separator_is_always_checked(self, tmp_path):
        """The concept exemption applies only to bare names."""
        path = tmp_path / "CLAUDE.md"
        path.write_text("see `docs/AGENTS.md`")
        assert not check_file(path, tmp_path).ok
