# Kavi prototype — common tasks
# Run from the repository root.

PY ?= uv run python

.PHONY: install check fmt

install: ## Install dependencies
	uv sync

check: ## Lint with ruff
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Format with ruff
	uv run ruff format .
	uv run ruff check --fix .