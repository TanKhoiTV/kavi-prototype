# Kavi prototype — common tasks
# Run from the repository root.

PY ?= uv run python

.PHONY: install check fmt bench bench-data

install: ## Install dependencies
	uv sync

check: ## Lint with ruff
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Format with ruff
	uv run ruff format .
	uv run ruff check --fix .

bench: ## Run the benchmark harness (offline smoke by default)
	uv run python -m bench.run --smoke --out bench-results

bench-data: ## Phase 1: build the lean eval set + manifest (needs network)
	uv run python -m bench.data_prep --out eval_manifest_v1.json
