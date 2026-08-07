"""Resolve extracted references against the repo.

Every check here is deterministic and local: path resolution, `PATH` lookup,
git metadata. No LLM call, no network, no embedding pass -- a staleness check
that costs an API call will not be run every session, and a check nobody runs
is worse than none.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .refs import Reference, RefKind, extract


@dataclass(frozen=True)
class Finding:
    """One reference that no longer resolves."""

    ref: Reference
    reason: str
    suggestion: str | None = None

    def format(self, file: Path) -> str:
        head = f"{file}:{self.ref.line_no}  {self.ref.kind}: {self.ref.value!r} — {self.reason}"
        if self.suggestion:
            head += f"\n    did you mean: {self.suggestion}"
        return head


def _git(root: Path, *args: str) -> str | None:
    """Run a git command, returning None if git is unavailable or fails."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _tracked_files(root: Path) -> set[str] | None:
    """Files git knows about. None when this is not a git repo.

    Preferred over walking the filesystem: it ignores build output and
    node_modules for free, and it is what a reader means by "in the repo".
    """
    out = _git(root, "ls-files")
    if out is None:
        return None
    return set(out.splitlines())


def _suggest(value: str, tracked: set[str] | None) -> str | None:
    """Find a moved file with the same basename.

    The common drift is a move, not a delete, and naming the new location is
    the difference between a report someone acts on and one they ignore.
    """
    if not tracked:
        return None
    base = Path(value).name
    if not base:
        return None
    matches = [p for p in tracked if Path(p).name == base]
    if len(matches) == 1:
        return matches[0]
    if 1 < len(matches) <= 3:
        return ", ".join(sorted(matches))
    return None


def check_path(ref: Reference, root: Path, tracked: set[str] | None) -> Finding | None:
    """Does this path exist in the repo?"""
    value = ref.value.rstrip("/")
    is_dir_claim = ref.value.endswith("/")
    target = (root / value).resolve()
    try:
        # Refuse to report on anything outside the repo: a context file may
        # legitimately mention a sibling project.
        target.relative_to(root.resolve())
    except ValueError:
        return None

    if target.exists():
        return None

    # A bare filename with no directory part is usually being named as a
    # concept rather than claimed to exist here -- "agents read CLAUDE.md and
    # AGENTS.md". Only report it when a file of that name exists somewhere in
    # the repo, which makes it a real reference to a moved file.
    #
    # A trailing slash is exempt from this: "`console/`" is an explicit claim
    # that a directory exists, not a concept being named.
    if "/" not in value and not is_dir_claim:
        suggestion = _suggest(value, tracked)
        if suggestion is None:
            return None
        return Finding(ref=ref, reason="path does not exist here", suggestion=suggestion)

    # A path may exist but be gitignored (build output, venvs). That is not
    # drift -- the file is there.
    return Finding(
        ref=ref,
        reason="path does not exist",
        suggestion=_suggest(value, tracked),
    )


def _declares_own_command(root: Path, exe: str) -> bool:
    """Is `exe` an entry point this project itself provides?

    A project documents its own CLI constantly, and that CLI is usually not on
    PATH during development (it lives in a venv, or is not installed yet).
    Flagging it is a guaranteed false positive on the tool's own README.
    """
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if f"{exe} =" in text or f'"{exe}"' in text:
            return True
    for manifest, key in (("package.json", '"bin"'), ("Cargo.toml", "[[bin]]")):
        path = root / manifest
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            if key in text and exe in text:
                return True
    return root.name == exe


def check_command(ref: Reference, root: Path) -> Finding | None:
    """Does this command resolve?

    Resolution only -- never execution. Running commands from a context file
    would be both slow and a code-execution hazard.
    """
    exe = ref.value
    # A relative path to a script in the repo.
    if "/" in exe:
        target = root / exe
        if target.exists():
            return None
        return Finding(ref=ref, reason="script not found")

    if shutil.which(exe):
        return None

    if _declares_own_command(root, exe):
        return None

    # Not on PATH. Could be a project-local tool the reader installs, so this
    # is reported at lower confidence than a missing path.
    return Finding(ref=ref, reason="command not found on PATH")


@dataclass
class Report:
    file: Path
    findings: list[Finding]
    checked: int

    @property
    def ok(self) -> bool:
        return not self.findings

    def format(self) -> str:
        if self.ok:
            return f"{self.file}: {self.checked} references checked, all resolve"
        lines = [f"{self.file}: {len(self.findings)} of {self.checked} references broken"]
        lines.extend("  " + f.format(self.file) for f in self.findings)
        return "\n".join(lines)


def check_file(path: Path, root: Path | None = None) -> Report:
    """Check every reference in one context file."""
    root = root or find_repo_root(path.parent)
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = extract(text)
    tracked = _tracked_files(root)

    findings: list[Finding] = []
    for ref in refs:
        if ref.kind is RefKind.PATH:
            found = check_path(ref, root, tracked)
        else:
            found = check_command(ref, root)
        if found:
            findings.append(found)

    return Report(file=path, findings=findings, checked=len(refs))


def find_repo_root(start: Path) -> Path:
    """Nearest ancestor containing .git, or `start` if there is none."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


CONTEXT_FILENAMES = (
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    "AGENT.md",
    ".cursorrules",
    ".windsurfrules",
)


def find_context_files(root: Path) -> list[Path]:
    """Locate context files, skipping vendored and build directories."""
    skip = {".git", "node_modules", ".venv", "venv", "target", "dist", "build", "__pycache__"}
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".venv")]
        for name in filenames:
            if name in CONTEXT_FILENAMES:
                found.append(Path(dirpath) / name)
    return sorted(found)
