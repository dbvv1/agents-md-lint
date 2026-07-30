# driftwatch

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Your agent is confidently answering from a stale index.** driftwatch watches the artifacts your agent trusts — `CLAUDE.md`, code indexes, knowledge graphs, generated docs, cached embeddings — and tells you when they no longer match the repo.

⭐ **Star us on GitHub** if your `CLAUDE.md` still describes a module you deleted.

> [!NOTE]
> **Status: In development.**

## Why this exists

Every agent workflow now depends on derived artifacts: a context file, a code index, a knowledge graph, a generated architecture doc, an embedding cache. All of them are snapshots. All of them rot. None of them tell you they've rotted.

The failure mode is the dangerous kind: the agent doesn't error, it answers — fluently, with citations, from a picture of your codebase that is weeks out of date. This is already the loudest complaint against the largest code-graph tools in the ecosystem: a stale index silently intercepts queries and returns confident wrong answers.

There is tooling for building these artifacts and essentially none for knowing when to distrust them.

## What it checks

| Artifact | Drift signal |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | Referenced paths, commands, and modules that no longer exist |
| Code indexes / knowledge graphs | Commits since build; files added, deleted, or moved since |
| Generated docs | Source files changed since the doc was written |
| Embedding caches | Fraction of cached chunks whose source has changed |
| Build/test commands in context files | Commands that no longer resolve or no longer pass |

Output is a staleness report and a non-zero exit code past a configurable threshold, so it drops into CI or a pre-commit hook.

## Install

```bash
pipx install driftwatch      # or: uv tool install driftwatch
driftwatch check
```

As a skill, so the agent checks its own context before trusting it:

```bash
npx skills add openintelligence-labs/driftwatch
```

Supported harnesses: Claude Code, Codex, Cursor, OpenCode, Gemini CLI, Copilot CLI, Aider, Cline, Continue, Amp, Kiro, OpenClaw, plus generic `.agents/skills`.

## Design stance

Drift detection must be **cheap and deterministic** — no LLM call, no network, no embedding pass. It runs on file mtimes, git history, path resolution, and content hashes. If checking staleness costs an API call, nobody will run it on every session, and a check nobody runs is worse than none.

It reports staleness; it does not rebuild. Rebuilding is the job of whatever produced the artifact.

## Roadmap

- [ ] Git-delta checks against artifact build timestamps
- [ ] `CLAUDE.md` / `AGENTS.md` reference validation (paths, commands, modules)
- [ ] Adapters for common index formats
- [ ] Embedding-cache staleness ratio
- [ ] Configurable thresholds + CI exit codes
- [ ] Pre-commit hook
- [ ] Skill packaging

## Part of the Open Intelligence Labs ecosystem

- [SecondBrain](https://github.com/openintelligence-labs/secondbrain) — bi-temporal knowledge graph; drift is a first-class concern there
- [awesome-claude-md](https://github.com/openintelligence-labs/awesome-claude-md) — what belongs in a context file; driftwatch checks it's still true
- [actants](https://github.com/openintelligence-labs/actants) — agent SDK

## License

MIT
