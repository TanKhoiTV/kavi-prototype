# Contributing to Kavi (kavi-prototype)

## Repository role

This is the **implementation** submodule of `aivoice-2026` (the umbrella repo).
It contains the code and internal docs; public-facing documentation belongs in
the parent. Third-party model weights and eval corpora are **not** committed —
they are fetched on demand (see [Models & data](#models--data)).

## Cloning

`kavi-prototype` is a **Git submodule** of the public parent repo
[`aivoice-2026`](https://github.com/TanKhoiTV/aivoice-2026). That means it does
**not** come down with a normal `git clone` of the parent. Both repositories are
public, so no access request is needed.

### 1. Clone the parent with the submodule in one step

```bash
git clone --recurse-submodules git@github.com:TanKhoiTV/aivoice-2026.git
cd aivoice-2026
```

No SSH key? Use HTTPS instead: `https://github.com/TanKhoiTV/aivoice-2026.git`.

### 2. Or clone first, then initialize the submodule

```bash
git clone git@github.com:TanKhoiTV/aivoice-2026.git
cd aivoice-2026
git submodule update --init --recursive
```

### 3. Enter the prototype

```bash
cd prototype          # you are now inside kavi-prototype
git checkout main     # submodules start on a detached commit; switch to a branch
```

### Keeping in sync

- After `git pull` in the **parent**, the submodule pointer may advance — run
  `git submodule update --recursive` (from the parent) to match it.
- To **update the pointer** after changing the submodule: from the **parent**,
  `git add prototype && git commit` so the new submodule commit is recorded.

### The Android app is not part of this repo

The Android app lives in a **separate private repository** (`kavi-android`) and
is deliberately not vendored here. There is no `android/` submodule in this repo
and `android/` is gitignored, so a clone never populates it. For Android work,
clone `kavi-android` separately (ask the owner for access).

`adb` ships with the Android **platform-tools**, not with this repo. On Windows,
install platform-tools (or Android Studio) and add `platform-tools\` to `PATH`.
The pinned NDK is r26c (`26.1.10909125`).

## Setup

Run everything from the repository root. The only prerequisite is `uv`
(<https://docs.astral.sh/uv/>).

```bash
make setup        # deps + model weights + FLEURS data + eval manifest
```

`make setup` is the **standard path**: every contributor ends up with the same
pinned artifacts. It needs network access and ~1.5 GB of downloads, and is
equivalent to:

```bash
uv sync           # create .venv from uv.lock (Python 3.12, CPU-only torch)
make models       # pinned Opus-MT vi->en weights + tokenizers  -> models/
make data         # pinned FLEURS vi_vn/en_us test parquets     -> eval_data/raw/
make bench-data   # build the eval manifest                     -> eval_data/eval_manifest_v1.json
```

Offline or bandwidth-constrained? `make setup-min` installs the dependencies and
builds the manifest from the built-in fallback eval set (MT + TTS only, no ASR
items — enough for `make bench` and `make test`).

Everyday commands:

```bash
make check        # ruff lint + format check (read-only; CI-safe)
make fmt          # auto-fix formatting
make test         # pytest (tests/ only)
make bench        # offline harness run (writes bench-results/)
```

## Models & data

Third-party artifacts are **not** committed (see [`NOTICE`](NOTICE)). Their
identity, revision and SHA-256 digests live in
[`assets.lock.toml`](assets.lock.toml), and the fetchers verify against it.

| Command | What it does | Download |
| ------- | ------------ | -------- |
| `make models` | `scripts/fetch_models.py` — `Helsinki-NLP/opus-mt-vi-en` at the pinned revision, converted to CTranslate2 int8 | ~289 MB |
| `make data` | `scripts/fetch_data.py` — `google/fleurs` `vi_vn` + `en_us` test parquets, resumable | ~1.1 GB |
| `make bench-data` | `bench/data_prep.py` — builds the manifest from whatever is in `eval_data/raw/` (offline) | — |
| `make verify-assets` | `scripts/verify_assets.py` — checks every downloaded file against `assets.lock.toml` | — |

Worth knowing:

- `make models` skips `tf_model.h5` (a redundant TensorFlow copy that
  CTranslate2 never reads) and verifies both the upstream checkpoint and the
  converted model.
- Both fetchers are **pinned**. To bump one: change the `revision` in
  `assets.lock.toml`, re-run the fetch, then update the digests reported by
  `make verify-assets`. Never point them at a moving branch.
- `make data` resumes interrupted downloads (`curl -C -`), so re-running is safe.
- `make bench` needs the model weights. Without them the harness does **not**
  abort — `bench/run.py` records an error per item instead. If results look
  empty, run `make verify-assets`.
- `HF_HOME` is honoured by `make models`, so you can relocate the Hugging Face
  cache if `~/.cache/huggingface` is on a small volume.
- The eval set is deterministic (FLEURS sampling is seeded with `42`), so
  results are comparable across machines **provided everyone runs `make setup`
  rather than mixing pinned and unpinned downloads**.

## Workflow

1. Branch from `main`: `git checkout -b feat/<topic>` (or `fix/`, `chore/`).
2. Make focused commits using **Conventional Commits**:
   - `feat:` new feature · `fix:` bugfix · `chore:` maintenance ·
     `docs:` documentation · `refactor:` restructure · `test:` tests.
3. Keep changes offline/on-device friendly.
4. Open a PR into `main`. Use the PR template.
5. Run `make check` and `make test` before pushing — CI runs both.

## Versioning

Releases follow **Semantic Versioning** (MAJOR.MINOR.PATCH) once the API
stabilizes.

## Prerequisites (detail)

- **Python 3.12** — pinned via `.python-version`; `uv` selects it automatically.
  If it is not installed, run `uv python install 3.12` first.
- **Network for the first `uv sync`** — packages come from PyPI, and
  `torch`/`torchaudio` fetch **CPU-only** wheels from the PyTorch CPU index
  (`https://download.pytorch.org/whl/cpu`, set in `pyproject.toml` under
  `[tool.uv] extra-index-url`). Allow outbound HTTPS to both hosts.
- **Disk** — budget ~2 GB for `.venv`, `models/`, and the FLEURS parquets.

The v0 harness runs **CPU-only** today (faster-whisper / CTranslate2 Opus-MT /
Piper-CPU). On-device QNN candidates land in Phase 4 — see
`docs/reference/phase-4-qnn-plan.md`.

## Tooling & standards

- **Commit messages**: enforced by [`commitlint`](https://commitlint.js.org/)
  via the `commit-msg` pre-commit hook. Titles must follow
  [Conventional Commits](https://www.conventionalcommits.org/). The same rule is
  checked in CI.
- **pre-commit**: install once with `uv run pre-commit install`. It also runs
  basic file hygiene (trailing whitespace, EOF newline, YAML, large files).
- **Linting / formatting**: [`ruff`](https://docs.astral.sh/ruff/) — run
  `make check` (lint + format check) before pushing; `make fmt` to auto-fix.
- **Tests**: `pytest`, configured to collect `tests/` only (`testpaths` in
  `pyproject.toml`) so local vendored trees cannot break the run.
- **Line endings**: governed by [`.gitattributes`](.gitattributes) — LF for
  scripts, `Makefile` and source, regardless of `core.autocrlf`.
- **Changelog**: [`git-cliff`](https://git-cliff.org/) generates `CHANGELOG.md`
  from Conventional Commits. CI regenerates it on every push to `main`.
- **CI**: `.github/workflows/ci.yml` runs `make check` and `make test` on
  PRs/pushes to `main`.
- **License**: MIT (see `LICENSE`). Third-party attributions: `NOTICE`.

## Development environments (OS notes)

The core toolchain is **OS-agnostic**: Python + `uv`, `ruff`, and Gradle all run
identically on Windows, Linux, and macOS. The OS-specific pieces are the
**QAIRT conversion toolchain** (Phase 4) and, in the Android repo, the
**Android SDK/NDK install**.

**You do not need a hybrid Windows + WSL2 machine — a single OS is enough:**

- **Windows-only** — install Python + `uv`, and (for Phase 4) the Windows QAIRT
  SDK; its converters run natively as `.exe`. No WSL required for the Python
  harness.
- **Linux-only** — same, with the Linux QAIRT SDK (`.qik` installed via
  `qpm-cli`); conversion runs natively.
- **macOS-only** — Python + `uv` work fine. The QAIRT *conversion* toolchain is
  Linux/Windows-only, so run conversion in a VM/container or CI and build the
  app from the committed context binaries.

### Windows specifics

- **`make` is not installed by default.** Install it (`winget install
  ezwinports.make`) or use the Git-for-Windows shell. If you would rather skip
  `make`, every target is a plain `uv run …` command — copy it from the
  `Makefile`.
- **QAIRT conversion on Windows**: dot-source `scripts\qairt-env.ps1` (the
  PowerShell counterpart of the Linux `scripts/qairt-env.sh`). It creates the
  Python 3.10 `.venv-qairt`, sets `PYTHONPATH`, locates the converter bin
  directory (which varies between SDK releases), and verifies the converters.
  It is less battle-tested than the Linux script — report your SDK layout if the
  bin directory is not found.
- **Environment variables**: `.kavi.env` uses bash `export` syntax and is meant
  for Git Bash/WSL. In PowerShell set the variables directly, or use
  `scripts\qairt-env.ps1`.

**Our setup (reference, not a requirement):** the assistant builds the Android
app on **Windows** and runs QAIRT conversion in **WSL2** — only because this
box's WSL environment cannot launch the Windows `.exe` converters. A human
Windows developer runs conversion natively on Windows; the split is an
environment quirk, not a project requirement.

**QAIRT conversion toolchain (Phase 4):** host build-time only, needed solely
when producing HTP v73 context binaries. See `docs/reference/phase-4-qnn-plan.md`
§1 for the exact env contract (`QAIRT_SDK_ROOT`, `ANDROID_NDK_ROOT`,
`qairt-env.sh`, `.venv-qairt`).

## Note on `archive/`

The previous implementation lives under `archive/`. It is reference material,
not active code — do not edit files there; re-implement in the new structure.
