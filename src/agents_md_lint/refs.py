"""Extract checkable references from a context file.

The hard part is not finding path-shaped strings -- it is not reporting the
ones that were never claims about the repo. A checker that cries wolf on prose
gets uninstalled after one run, so every extractor here is deliberately
conservative and the false-positive cases are listed as tests.

Only two reference kinds are extracted, because only these two can be verified
cheaply and unambiguously:

  PATH     a repo-relative file or directory the file says exists
  COMMAND  a shell command the file tells you (or an agent) to run
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class RefKind(StrEnum):
    PATH = "path"
    COMMAND = "command"


@dataclass(frozen=True)
class Reference:
    """One checkable claim, with the line it came from for reporting."""

    kind: RefKind
    value: str
    line_no: int
    line: str


# A path-shaped token inside backticks. Requires either a directory separator
# or a file extension: bare words like `pytest` are commands or prose, not
# paths, and treating them as paths was the largest false-positive source.
_PATH_IN_TICKS = re.compile(r"`([^`\n]+)`")

# Fenced code blocks are where commands live. Prose backticks are not commands.
_FENCE = re.compile(r"^```(\w*)\s*$")

# Leading shell prompt characters to strip. Deliberately excludes '#': in a
# shell fence that is a comment, not a root prompt, and stripping it turned
# "# install first" into the command "install".
_PROMPT = re.compile(r"^[$>]\s+")

# Things that look like paths but are not claims about this repo.
_NOT_A_PATH = re.compile(
    r"""
    ^(?:https?|git|ssh|mailto|file)://   # URLs
  | ^~                                    # home-relative
  | ^/(?:usr|etc|opt|var|tmp|bin|sbin|proc|dev)(?:/|$)  # system paths
  | ^[A-Z]:[\\/]                          # windows absolute
  | ^\.{3}                                # ellipsis
  | \*                                    # globs -- cannot resolve one path
  | ^\$                                   # shell variables
  | ^<.*>$                                # <placeholder>
  """,
    re.VERBOSE,
)

# A template segment is not a concrete repo path, including when nested in a
# longer path. Keep this path-only: command extraction has its own contract.
_PLACEHOLDER = re.compile(r"<[^<>/\s]+>")

# Extensions that indicate a file reference even without a separator.
_FILE_EXT = re.compile(
    r"\.(?:py|js|ts|tsx|jsx|rs|go|java|rb|c|h|cpp|hpp|sh|bash|zsh|fish"
    r"|toml|yaml|yml|json|md|txt|cfg|ini|env|lock|sql|proto|graphql"
    r"|html|css|scss|vue|svelte|swift|kt|scala|ex|exs|php|pl|lua|r)$",
    re.IGNORECASE,
)

# Commands that only make sense against the network or the user's machine.
# Checking whether these "resolve" says nothing about repo health.
_UNCHECKABLE_COMMANDS = frozenset(
    {"curl", "wget", "ssh", "scp", "sudo", "open", "docker", "kubectl", "gh", "git"}
)


def _looks_like_path(token: str) -> bool:
    """Is this token a claim that a repo path exists?"""
    if not token or token.isspace():
        return False
    if _NOT_A_PATH.search(token) or _PLACEHOLDER.search(token):
        return False
    if " " in token.strip():
        # Multi-word backtick content is prose or a command, not a path.
        return False
    return "/" in token or bool(_FILE_EXT.search(token))


def extract_paths(text: str) -> list[Reference]:
    """Repo-relative paths the file claims exist.

    Only backticked tokens are considered. Unquoted prose mentions of a
    filename are too ambiguous to check without false positives.
    """
    refs: list[Reference] = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            # Inside a fence, backticks are not markup and the content is a
            # command; handled by extract_commands.
            continue
        for token in _PATH_IN_TICKS.findall(line):
            token = token.strip()
            if _looks_like_path(token):
                # The trailing slash is preserved: "`console/`" is a claim
                # that a directory exists, while a bare "`AGENTS.md`" is
                # usually naming a concept. check.py needs that distinction.
                refs.append(Reference(RefKind.PATH, token, i, line.strip()))
    return refs


def extract_commands(text: str) -> list[Reference]:
    """Commands the file tells someone to run.

    Only the first word matters -- whether the executable resolves. Argument
    validity is not checkable without running it, which this tool never does.
    """
    refs: list[Reference] = []
    in_fence = False
    lang = ""
    for i, line in enumerate(text.splitlines(), start=1):
        fence = _FENCE.match(line.strip())
        if fence:
            if not in_fence:
                lang = fence.group(1).lower()
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        # Only shell-ish fences contain commands. A ```python block is code.
        if lang not in ("", "sh", "bash", "shell", "zsh", "console", "terminal"):
            continue

        stripped = _PROMPT.sub("", line.strip())
        if not stripped or stripped.startswith("#"):
            continue
        # Take the first word of the first command in a pipeline/chain.
        head = re.split(r"[|;&]|&&", stripped)[0].strip()
        # Skip env-var assignments: FOO=bar cmd
        parts = [p for p in head.split() if "=" not in p.split("/")[0]]
        if not parts:
            continue
        exe = parts[0]
        if exe in _UNCHECKABLE_COMMANDS:
            continue
        if _NOT_A_PATH.search(exe):
            continue
        refs.append(Reference(RefKind.COMMAND, exe, i, line.strip()))
    return refs


def extract(text: str) -> list[Reference]:
    """All checkable references, in line order."""
    refs = extract_paths(text) + extract_commands(text)
    return sorted(refs, key=lambda r: (r.line_no, r.kind))
