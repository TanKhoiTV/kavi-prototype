# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this repo is

- **Kavi** — offline on-device speech-to-speech translation (VI↔EN), for the
  OneVoice AI Challenge.
- This is the **private implementation submodule** of `aivoice-2026`. It holds
  all code, model weights, and internal docs.

## Repository visibility

- **Parent `aivoice-2026`** is **public** and hosts documentation + CI.
- **This repo (`kavi-prototype`)** is **private** and holds code, models, and
  internal docs. Do not move private implementation details into the public
  parent.

## Layout (current)

- `models/` — MT weights at root (kept for reuse; see `.gitignore`).
- `voices/` — Piper TTS voice models.
- `bench/` — v0 benchmark harness (candidate adapters, scorer, eval-manifest schema, data prep).
- `docs/` — internal docs.
- `eval_data/` — generated eval audio / downloaded corpora.
- `experiments/` — slot for pipeline experiments.
- `archive/` — the entire previous implementation, preserved for reference.
  Read here before re-implementing anything.
- `src/` — (planned) new application code — not yet scaffolded.

## Conventions

- Commits follow **Conventional Commits** (`feat:`, `fix:`, `chore:`, …).
- Branch per task: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`; PR into
  `main`.
- Run `make check` (ruff) before committing; `make test` for the bench harness suite.
- Keep the project **fully offline / on-device**: no network calls at runtime.

## Working here

1. Check `archive/` first — much of the prior logic is reusable.
2. Prefer reusing `models/` weights over re-downloading.
3. Keep the public/private boundary: internal notes stay here, not in the parent.
4. Benchmark harness: `make bench-data` (build eval set), `make bench` (run),
   `make test` (suite) — see `bench/` + `docs/benchmarking-*.md`.
