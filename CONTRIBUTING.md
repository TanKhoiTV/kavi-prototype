# Contributing to Kavi (kavi-prototype)

## Repository role

This is the **private implementation** submodule of `aivoice-2026` (public
parent). It contains code, models, and internal docs. Public-facing
documentation belongs in the parent repo.

## Cloning

`kavi-prototype` is a **Git submodule** of the public parent repo
[`aivoice-2026`](https://github.com/TanKhoiTV/aivoice-2026). That means it
does **not** come down with a normal `git clone` of the parent — you must
recurse into submodules, and because this repo is **private** you also need
read access to it (ask the owner to be added as a collaborator) plus working
Git credentials (SSH key or token) for `github.com`.

### 1. Clone the parent with the submodule in one step

```bash
git clone --recurse-submodules git@github.com:TanKhoiTV/aivoice-2026.git
cd aivoice-2026
```

### 2. Or clone first, then initialize the submodule

```bash
git clone git@github.com:TanKhoiTV/aivoice-2026.git
cd aivoice-2026
git submodule update --init --recursive
```

### 3. Enter the prototype

```bash
cd prototype        # you are now inside the private kavi-prototype repo
git checkout main  # submodules start on a detached commit; switch to a branch
```

### Keeping in sync

- After `git pull` in the **parent**, the submodule pointer may advance — run
  `git submodule update --recursive` (from the parent) to match it.
- To **update the pointer** after changing the submodule: from the **parent**,
  `git add prototype && git commit` so the new submodule commit is recorded.
- Authentication: the submodule is private, so use SSH
  (`git@github.com:...`) with an SSH key registered on GitHub, or HTTPS with a
  personal access token.

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
