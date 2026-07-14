# Contributing to Kavi (kavi-prototype)

## Repository role

This is the **private implementation** submodule of `aivoice-2026` (public
parent). It contains code, models, and internal docs. Public-facing
documentation belongs in the parent repo.

## Workflow

1. Branch from `main`: `git checkout -b feat/<topic>` (or `fix/`, `chore/`).
2. Make focused commits using **Conventional Commits**:
   - `feat:` new feature · `fix:` bugfix · `chore:` maintenance ·
     `docs:` documentation · `refactor:` restructure · `test:` tests.
3. Keep changes offline/on-device friendly.
4. Open a PR into `main`. Use the PR template.
5. Run `make check` before pushing.

## Versioning

Releases follow **Semantic Versioning** (MAJOR.MINOR.PATCH) once the API
stabilizes.

## Local setup

```bash
uv sync        # install dependencies
make check     # lint
```

## Note on `archive/`

The previous implementation lives under `archive/`. It is reference material,
not active code — do not edit files there; re-implement in the new structure.
