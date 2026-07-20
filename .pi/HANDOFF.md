# HANDOFF

> Generated from `.pi/prompts/handoff.md`. Comprehensive enough that a fresh
> session can continue without reading the source conversation.
> Project background (Kavi, the contest, architecture): see `.pi/AGENTS.md`
> and `docs/onboarding.md`.

## Goal

Make the `prototype` (kavi-prototype) submodule robust for agent sessions that
are **scoped to the submodule only** (cwd = `prototype/`), and keep the parent
`aivoice-2026` submodule pointer consistent after prototype merges.

This session's concrete wins:
- Relocated `AGENTS.md` into `.pi/` (pi agent config dir).
- Made the parent's two doc files readable **locally inside the submodule**, so a
  scoped agent needs no parent-location knowledge.
- (Earlier, already merged to `main`) promoted runtime deps, pinned Python 3.12,
  normalized the `dev` array to uv's canonical form, and ignored caches.

## Current branch / state

- Repo: `prototype` (TanKhoiTV/kavi-prototype submodule).
- Branch: **`chore/move-agents-md-to-pi`** — created off `main` @ `a2da655`.
- Local HEAD: **`8ce93d9`** (handoff prompt). **Unpushed, unmerged.**
- Parent `aivoice-2026`: `main` @ `2c51406`; its submodule gitlink still points
  at `a2da655` — it does **not** yet include this branch's commits.
- Working tree right now: `.pi/prompts/handoff.md` (committed), `.pi/HANDOFF.md`
  (this file, new/untracked).

## Files changed (this branch, cumulative)

- `.pi/AGENTS.md` — moved from repo root (commit `7441a01`); content revised
  (commit `79f8234`).
- `docs/onboarding.md` — "Repository layout" row updated to point at
  `.pi/AGENTS.md` (commit `18cac13`).
- `docs/contest-info.md` — NEW, mirrored verbatim from parent
  `aivoice-2026/docs/` (commit `f71d896`).
- `docs/specifications.md` — NEW, mirrored verbatim from parent (commit `f71d896`).
- `.pi/prompts/handoff.md` — NEW agent prompt (commit `8ce93d9`).
- `.pi/HANDOFF.md` — NEW handoff doc (created this step, untracked).

## Decisions made

- **`AGENTS.md` → `.pi/AGENTS.md`**: pi agent config belongs in `.pi/`.
- **No parent mention in AGENTS.md**: instead of pointing agents at the parent
  repo, the parent's two doc files (`contest-info.md`, `specifications.md`) are
  duplicated into `prototype/docs/` for local visibility. Reason: a
  `prototype/`-scoped agent session cannot reliably locate the parent — submodule
  gitlinks never auto-update, and `git rev-parse --show-toplevel` returns the
  submodule, not the parent (the parent is discoverable only via
  `git rev-parse --show-superproject-working-tree` or `../.gitmodules`).
  Duplication removes the need for parent-location knowledge.
- **Mirrors may drift**: the duplicated docs are intentional copies; accepted
  trade-off vs. maintaining a pointer. Refresh from parent later if needed.
- **uv canonical form**: the `[dependency-groups]` `dev` array is kept in uv's
  single-line canonical form (commit `e52377b`, PR #68) so future `uv sync`
  doesn't leave an uncommitted reformat.
- **(Prior, merged)** `pyarrow`/`ctranslate2`/`numpy` promoted to direct deps;
  `.python-version` = `3.12`; `CONTRIBUTING.md` documents Python + network
  prereqs (PR #67). `*cache/` ignored + pyright dot-dir excludes (PR #66).

## Commands run (key)

- `git mv AGENTS.md .pi/AGENTS.md`
- `uv sync` / `uv lock` (attempted to trigger uv's reformat — see What failed)
- `gh pr create` / `gh pr checks <n> --watch` / `gh pr merge <n> --rebase --delete-branch`
  for PRs #66, #67, #68.
- Parent sync pattern:
  `cd aivoice-2026 && cd prototype && git checkout <tip> && git checkout -- . && cd .. && git add prototype && git commit && git push`

## What failed

- `uv remove datasets` errored ("datasets is in the dev group"); the following
  `uv add datasets` then wrongly added `datasets>=2.19.1` to `[project.dependencies]`
  and churned `uv.lock`. Reverted with `git checkout -- pyproject.toml uv.lock`,
  then applied uv's exact canonical single-line `dev` array manually (verified
  byte-identical blob `3b53274`).
- `git checkout main` aborted because `uv sync` had left an uncommitted reformat
  of `pyproject.toml`; resolved by discarding that reformat first.
- A submodule pointer sync was initially missed because a `prototype/`-scoped
  flow doesn't touch the parent — the parent must be synced explicitly from
  `aivoice-2026` after every prototype merge.

## What remains

- `chore/move-agents-md-to-pi` is **unpushed and unmerged** (5 commits + this
  handoff file).
- Parent `aivoice-2026` gitlink still at `a2da655` — must be bumped after this
  branch merges into `prototype` main.
- `.pi/HANDOFF.md` is currently **untracked** (not yet committed).

## Exact next step

1. `git push -u origin chore/move-agents-md-to-pi`
2. `gh pr create --base main --head chore/move-agents-md-to-pi` (CI runs
   `make check` + `make test`).
3. `gh pr checks <n> --watch` → `gh pr merge <n> --rebase --delete-branch`.
4. In `aivoice-2026`: `cd prototype && git fetch && git checkout <new-main-tip> &&
   git checkout -- . && cd .. && git add prototype && git commit -m "chore: bump
   prototype submodule to agents-md-in-pi + parent docs mirror" && git push`.
5. (Optional) commit `.pi/HANDOFF.md` too, or delete it once the branch is
   merged and the work is picked up.
