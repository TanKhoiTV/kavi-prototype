# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this repo is

- **Kavi** — offline on-device speech-to-speech translation (VI↔EN), for the OneVoice AI Challenge.
- This repo is _private_ and holds code, models, and internal docs. Do not move private implementation details into the public parent.

## Layout (current)

- `models/` — MT weights at root (kept for reuse; see `.gitignore`).
- `voices/` — Voice models.
- `bench/` — v0 benchmark harness (candidate adapters, scorer, eval-manifest schema, data prep).
- `docs/` — internal docs.
- `eval_data/` — generated eval audio / downloaded corpora.
- `archive/` — the entire previous implementation, preserved for reference.

## Conventions

- Commits follow **Conventional Commits** (`feat:`, `fix:`, `chore:`, …).
- Branch per task: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`; PR into `main`.
- Run `make check` (ruff) before committing; `make test` for the bench harness suite.
- Keep the project **fully offline / on-device**: no network calls at runtime.

## Working here

1. Check `archive/` first for reusable logic.
2. Prefer reusing `models/` weights over re-downloading.
3. Keep the public/private boundary: internal notes stay here, not in the parent.
4. Benchmark harness: `make bench-data` (build eval set), `make bench` (run),
   `make test` (suite) — see `bench/` + `docs/benchmarking-*.md`.

## Compact Instructions

When compacting, preserve working state for continuation. Always keep:

- Current goal and acceptance criteria
- Exact files changed, created, deleted, or inspected and why
- Important hooks, functions, classes, routes, settings, commands, and config keys
- Business rules and architectural decisions
- Rejected approaches and why they were rejected
- Errors, failed tests, commands run, and fixes attempted
- Pending tasks and the exact next step

Summarize:

- Completed exploration
- Older discussion
- Repeated command output

Drop:

- Verbose logs except unresolved errors
- Duplicate explanations
- Deprecated and abandoned ideas

After compaction, re-read PLAN.md or HANDOFF.md if present before continuing.
