# Kavi prototype — common tasks
# Run from the repository root.
#
# Every command goes through `uv run`, so you do NOT need an activated
# virtualenv — just have uv installed (https://docs.astral.sh/uv/).
#
# check  vs  fmt:
#   - check is READ-ONLY: it verifies formatting and linting and exits
#     non-zero on any drift. Safe to run in CI.
#   - fmt MUTATES files: it reformats the tree and applies ruff autofixes.
#     Do not run it blindly in CI.
#
# setup / models / data  (asset acquisition; all NEED NETWORK on first run):
#   - setup          one-time bootstrap: uv sync + models + data + bench-data.
#   - setup-min      bootstrap without downloads (offline fallback eval set).
#   - models         fetch pinned Opus-MT weights + tokenizers -> models/.
#   - data           fetch pinned FLEURS test parquets         -> eval_data/raw/.
#   - verify-assets  verify downloaded digests against assets.lock.toml.
#
# vad-run  vs  vad-smoke  (VAD-only; no ASR/MT/TTS; needs eval_data/ + assets/noise/):
#   - vad-run runs ONE (THRESHOLD, TIMEOUT_MS) configuration over every item in
#     eval_data/vad_manifest_v2.json. Override: make vad-run THRESHOLD=0.1 TIMEOUT_MS=350
#   - vad-smoke runs the ADR default configuration on 1 VI + 1 EN item per
#     condition x SNR x pause cell. It is NOT the sweep.
#
# bench  vs  bench-data:
#   - bench runs a lightweight, OFFLINE --smoke pass by default and writes
#     results to bench-results/. This matches the project's offline /
#     on-device-at-runtime requirement.
#   - bench-data builds the eval manifest (eval_data/eval_manifest_v1.json)
#     from whatever is in eval_data/raw/ -- offline, with a built-in fallback
#     (MT + TTS only) when the FLEURS parquets are absent.

.PHONY: install setup setup-min check fmt test bench bench-data models data verify-assets vad-run vad-smoke

install: ## Install dependencies
	uv sync

setup: ## One-time bootstrap: deps + model weights + FLEURS data + manifest (NEEDS NETWORK)
	uv sync
	$(MAKE) models
	$(MAKE) data
	$(MAKE) bench-data

setup-min: ## Bootstrap without downloads (offline fallback eval set)
	uv sync
	$(MAKE) bench-data

check: ## Read-only lint/format check (CI-safe; verifies, no mutation)
	uv run ruff check .
	uv run ruff format --check .
	uv run pre-commit run yamllint --all-files

fmt: ## Format + autofix (mutates files)
	uv run ruff format .
	uv run ruff check --fix .

test: ## Run the test suite (pytest)
	uv run pytest

bench: ## Offline harness run (--smoke by default; writes bench-results/)
	uv run python -m bench.run --smoke --out bench-results

bench-data: ## Build eval manifest from local data (offline; fallback if absent)
	uv run python -m bench.data_prep --out eval_data/eval_manifest_v1.json

models: ## Fetch pinned Opus-MT weights + tokenizers (NEEDS NETWORK, ~290 MB)
	uv run python -m scripts.fetch_models --out models

data: ## Fetch pinned FLEURS test parquets (NEEDS NETWORK, ~1.1 GB, resumable)
	uv run python -m scripts.fetch_data --workdir eval_data

verify-assets: ## Verify downloaded models/data against assets.lock.toml
	uv run python -m scripts.verify_assets

THRESHOLD ?= 0.05
TIMEOUT_MS ?= 500

vad-run: ## One energy-VAD configuration over the full VAD manifest (THRESHOLD, TIMEOUT_MS)
	uv run python -m bench.vad_runner --threshold $(THRESHOLD) --timeout-ms $(TIMEOUT_MS) --out bench-results/vad

vad-smoke: ## VAD smoke test: default config, 1 VI + 1 EN item per cell (not the sweep)
	uv run python -m bench.vad_runner --per-cell-per-lang 1 --out bench-results/vad-smoke
