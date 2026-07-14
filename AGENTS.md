# AGENTS.md — Kavi

Guidance for humans and coding agents contributing to Kavi.

## What this is

Kavi is an offline, on-device speech-to-speech translator (Vietnamese ↔ English)
built for the OneVoice AI Challenge (Saigon AI Hub × Qualcomm, 2026). The full
pipeline is VAD → ASR → MT → TTS and runs entirely on a Snapdragon 8 Gen 2
Android phone with no cloud dependency.

This file lives in the `prototype/` submodule, which is the real project (code + documentation). The
parent repo (`aivoice-2026`) is a **public** umbrella that hosts the project's documentation entry point.

## Repository visibility

- `aivoice-2026` (this parent repo) is **public** and is the documentation-facing entry point for the project.
- `prototype/` (the submodule, `kavi-prototype` on GitHub) is **private** and contains the real implementation — code, models, and `docs/`.

Keep implementation details and any secrets out of the public parent repo.

## Where things are

- Code: `audio.py`, `pipeline.py`, `server.py`, `eval.py`, `main.py`
- Docs: `docs/` — see `docs/README.md` for the index
- Experiments: `experiments/`
- Models / data: `models/`, `refs/`, `voices/`, `logs/`

## How to work here

- Install deps: `uv sync`
- Smoke test: `make test` (runs `eval.py` on `greeting_vi.wav`)
- Full check: `make check` (sync → lint → typecheck → test)

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/);
  scopes and versioning are in `CONTRIBUTING.md`.
- All project documentation lives in the submodule's `docs/` — keep it there, not in the public parent.
- `prototype/` is a git submodule: after cloning run `git submodule update --init`
  (or clone with `--recurse-submodules`).
