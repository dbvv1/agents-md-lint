# driftwatch — Design

**Status:** design only. **Last updated:** 2026-07-30

## Problem

Agent workflows depend on derived artifacts — context files, code indexes, knowledge graphs, generated docs, embedding caches. All are snapshots; all rot; none report their own staleness. The failure mode is silent: the agent answers fluently from a weeks-old picture of the codebase.

This is the most-complained-about behavior in the largest code-graph tools, where a stale index intercepts queries and returns confident wrong answers.

## Design stance

**Cheap and deterministic.** Git history, file mtimes, path resolution, content hashes. No LLM call, no network, no embedding pass. A staleness check that costs an API call will not be run on every session, and a check nobody runs is worse than none.

**Reports, never rebuilds.** Rebuilding belongs to whatever produced the artifact.

## Checks

| Artifact | Signal |
|---|---|
| `CLAUDE.md` / `AGENTS.md` | Referenced paths, commands, modules that no longer resolve |
| Code index / KG | Commits since build; files added/deleted/moved since |
| Generated docs | Source changed since doc written |
| Embedding cache | Fraction of cached chunks whose source changed |
| Build/test commands | Commands that no longer resolve |

## Output

Staleness report plus a non-zero exit past a configurable threshold, so it drops into CI or a pre-commit hook.

## Honest ceiling

This sits in the observability/tooling band, where measured open-source attention tops out in the low thousands of stars. Included for utility, not reach.

## Milestones

0. Git-delta checks against artifact build timestamps
1. Context-file reference validation
2. Index-format adapters
3. Embedding-cache staleness ratio
4. Thresholds, CI exit codes, pre-commit hook
