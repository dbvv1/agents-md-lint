"""CLI input contracts: no input is different from a valid empty directory."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def run_cli(tmp_path):
    # Isolate root discovery from any Git marker in the system temp ancestors.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    def run(*args):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        return subprocess.run(
            [sys.executable, "-m", "agents_md_lint.cli", "check", *map(str, args)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    return run


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("target", ["MISSING.md", "missing-directory/"])
def test_missing_explicit_input_is_an_error(tmp_path, run_cli, target, json_output):
    args = [tmp_path / target]
    if json_output:
        args.append("--json")
    result = run_cli(*args)
    assert result.returncode == 2
    assert "input path does not exist:" in result.stderr
    assert str(tmp_path / target) in result.stderr
    assert not result.stdout


@pytest.mark.parametrize("json_output", [False, True])
def test_existing_empty_directory_keeps_success_contract(tmp_path, run_cli, json_output):
    args = [tmp_path]
    if json_output:
        args.append("--json")
    result = run_cli(*args)
    assert result.returncode == 0
    assert "no context files found under" in result.stderr
    assert not result.stdout


def test_existing_file_returns_a_real_json_report(tmp_path, run_cli):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("", encoding="utf-8")
    target = tmp_path / "AGENTS.md"
    target.write_text("`src/main.py`", encoding="utf-8")
    result = run_cli(target, "--json")
    assert result.returncode == 0
    report = json.loads(result.stdout)["reports"][0]
    assert report["checked"] == 1
    assert report["findings"] == []
    assert not result.stderr


def test_missing_reference_and_threshold_contract_remain(tmp_path, run_cli):
    target = tmp_path / "AGENTS.md"
    target.write_text("`src/gone.py`", encoding="utf-8")
    result = run_cli(target, "--json")
    assert result.returncode == 1
    report = json.loads(result.stdout)["reports"][0]
    assert report["checked"] == 1
    assert report["findings"][0]["value"] == "src/gone.py"
    assert run_cli(target, "--threshold", "1").returncode == 0
