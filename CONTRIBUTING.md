# Contributing to Kavi

Kavi's code and documentation live in this repository — the `prototype/`
submodule of the `aivoice-2026` umbrella repo.

## Versioning

This project uses **Semantic Versioning** (`MAJOR.MINOR.PATCH`).
Breaking changes increment MAJOR; backwards-compatible features increment MINOR;
patches and bugfixes increment PATCH.

## Commit Convention

All commits follow **Conventional Commits**:

```
<type>(<scope>): <description>
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `style`

**Scope:** optional — use `pipeline`, `eval`, `audio`, `server`, `docs`, `adr`, ...

```bash
feat(pipeline): add language-pair routing
docs(adr): record Hy-MT decision
```

## Local Development

Both repos are **private** — ask a maintainer to add you as a collaborator.

```bash
# from the umbrella repo:
git clone --recurse-submodules <repo-url>
cd aivoice-2026/prototype
uv sync
make test
```

## Branching

Work on a feature branch, open a PR against `main`, and ensure `make check`
passes before requesting review.
