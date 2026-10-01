# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this repo is

- **Kavi** — offline on-device speech-to-speech translation (VI↔EN), for the OneVoice AI Challenge.
- This repo is **public**, as is the parent `aivoice-2026`. The Android app lives in the
  separate private `kavi-android` repo. Never commit secrets, credentials, or private
  implementation details here (`.kavi.env` is gitignored for this reason).

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
3. Keep the public/private boundary: this repo and its parent are both **public**, so
   private implementation details belong in the private `kavi-android` repo.
4. Benchmark harness: `make bench-data` (build eval set), `make bench` (run),
   `make test` (suite) — see `bench/`. The notes in
   `docs/reference/benchmarking-*.md` are **cold reference** (the corpus catalog
   is still consulted for eval work); `docs/README.md` indexes what is current.
5. PR/review status: `scripts/pr_status.sh` prints your review inbox and outbox in
   one call. The inbox is inferred (open + not yours + unreviewed) — do **not** trust
   `--review-requested` alone here, since PRs are often opened with no reviewer
   requested and that query then reports "nothing to review".
6. Changelog commits are pushed with a **GitHub App** token, not `GITHUB_TOKEN`:
   `github-actions[bot]` cannot be a ruleset bypass actor, so the default token is
   rejected by the `main` ruleset. Read the header comment in
   `.github/workflows/changelog.yml` before editing that workflow — reverting to
   `GITHUB_TOKEN` reinstates a hard `GH013` push failure.

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
