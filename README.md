# agents-md-lint

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Your `CLAUDE.md` is lying to your agent.** agents-md-lint finds the paths and commands your context file claims exist — and no longer do.

⭐ **Star us on GitHub** if your `CLAUDE.md` still describes a module you deleted.

```bash
pipx install agents-md-lint && agents-md-lint check
```

```
CLAUDE.md: 5 of 6 references broken
  CLAUDE.md:14  path: 'src/proxy/' — path does not exist
  CLAUDE.md:18  path: 'src/main.rs' — path does not exist
    did you mean: crates/tokenmiser/src/main.rs
```

That output is real. It is [TokenMiser](https://github.com/openintelligence-labs/tokenmiser),
whose context file described a `src/` layout for months after the code moved to
a Rust workspace under `crates/`.

## Why this exists

Every agent workflow depends on a context file, and the failure mode is the
dangerous kind: the agent doesn't error, it *answers*. Fluently, confidently,
from a description of your repo that stopped being true three refactors ago.

Nobody notices, because nothing breaks loudly. The file just quietly stops
matching the code.

## What it checks

| Reference | Check |
|---|---|
| Paths in backticks — `` `src/api/` `` | Does it exist? If it moved, where to? |
| Commands in shell fences | Does the executable resolve? |

Non-zero exit past a threshold, so it drops into CI or a pre-commit hook.
An input path that does not exist exits 2; an existing directory without any
context files remains a successful no-op (reported on stderr):

```yaml
- run: pipx install agents-md-lint && agents-md-lint check
```

## Design stance

**Cheap and deterministic.** Path resolution, `PATH` lookup, `git ls-files`.
No LLM call, no network, no embedding pass, zero runtime dependencies. A
staleness check that costs an API call will not be run every session, and a
check nobody runs is worse than none.

**False positives are the failure mode.** A linter that flags prose gets
uninstalled after one run, so the extractor is deliberately conservative and
most of the test suite is cases it must stay *quiet* about — URLs, globs,
`~/paths`, `<placeholders>`, `$VARS`, system paths, prose in backticks,
`” ```python ”` blocks, shell comments, and a project's own CLI (which is
rarely on `PATH` during development).

Two of those were found by running agents-md-lint on its own `CLAUDE.md`.

**Reports, never rebuilds.** Fixing the file is your job; it knows what you
meant, and this tool doesn't.

## Measured on real repositories

Run across the Open Intelligence Labs monorepo:

| | |
|---|---:|
| Context files checked | 14 |
| References checked | 96 |
| Findings | 30 |
| **False positives** | **0** |

Every one of the 30 findings was verified by hand against the filesystem. The
two most interesting: a Rust project documenting a `src/` layout that had
become `crates/`, and a project listing a `console/` directory that was never
built.

Most of the rest are scaffolds whose context files describe a planned layout.
That is arguably not "drift" — it is a file written ahead of the code — but the
tool cannot tell intent from absence, and reporting it is the honest behaviour.

## Install

```bash
pipx install agents-md-lint     # or: uv tool install agents-md-lint
```

```bash
agents-md-lint check               # every context file under .
agents-md-lint check CLAUDE.md     # one file
agents-md-lint check --json        # machine-readable
agents-md-lint check --threshold 3 # tolerate up to 3 findings
```

## Honest limits

**This checks two things.** Paths and commands. It does not check whether your
architecture description is still accurate, whether a documented convention is
still followed, or whether the advice is any good — those need judgement, and
judgement needs an LLM, which is explicitly out of scope.

**Unquoted references are not checked.** "edit the main.py file" is invisible
to it. Backticks are the signal that something is a reference rather than
prose, and without that signal the false-positive rate is unacceptable.

**Commands are resolved, never run.** Whether `pytest` exists is checkable;
whether it passes is not, and running commands out of a context file would be a
code-execution hazard.

**The category ceiling is low.** Developer tooling of this kind tops out in the
low thousands of stars. This exists because it is useful and finishable, not
because it is a growth play.

## Roadmap

- [x] Path and command checks with move suggestions
- [x] JSON output, thresholds, CI exit codes
- [ ] Code index / knowledge graph staleness (commits since build)
- [ ] Generated-doc staleness (source changed after doc written)
- [ ] Embedding-cache staleness ratio
- [ ] Pre-commit hook

## Part of the Open Intelligence Labs ecosystem

- [TokenMiser](https://github.com/openintelligence-labs/tokenmiser) — LLM cost control
- [actants](https://github.com/openintelligence-labs/actants) — agent SDK

## License

MIT
