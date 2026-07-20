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
# bench  vs  bench-data:
#   - bench runs a lightweight, OFFLINE --smoke pass by default and writes
#     results to bench-results/. This matches the project's offline /
#     on-device-at-runtime requirement (see AGENTS.md).
#   - bench-data NEEDS NETWORK: it is the one-time Phase 1 step that builds
#     the eval manifest (eval_manifest_v1.json). Run it once, then `bench`
#     runs fully offline.

.PHONY: install check fmt test bench bench-data

install: ## Install dependencies
	uv sync

check: ## Read-only lint/format check (CI-safe; verifies, no mutation)
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Format + autofix (mutates files)
	uv run ruff format .
	uv run ruff check --fix .

test: ## Run the test suite (pytest)
	uv run pytest

bench: ## Offline harness run (--smoke by default; writes bench-results/)
	uv run python -m bench.run --smoke --out bench-results

bench-data: ## Phase 1: build eval manifest (NEEDS NETWORK, one-time)
	uv run python -m bench.data_prep --out eval_manifest_v1.json
