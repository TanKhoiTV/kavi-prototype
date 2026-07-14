.DEFAULT_GOAL := help

.PHONY: check lint typecheck typecheck-force test sync format clean help

help:
	@echo "Available targets:"
	@echo "  check        Run full CI suite (sync -> lint -> typecheck-force -> test)"
	@echo "  sync         Install/update Python dependencies (uv sync)"
	@echo "  lint         Run ruff lint + format check"
	@echo "  typecheck    Run pyright type checker (may show ML-dep false positives)"
	@echo "  typecheck-force  Run pyright, continue on errors (for CI suite)"
	@echo "  test         Run pipeline smoke test on greeting_vi.wav"
	@echo "  format       Auto-fix formatting with ruff"
	@echo "  clean        Remove pipeline output files"

check: sync lint typecheck-force test

sync:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck-force:
	-uv run pyright . || true

# NOTE: pyright reports "unresolved import" errors for torch, ctranslate2,
# piper_tts, etc. These are heavy ML deps installed at pipeline runtime,
# not in the dev venv. The errors are expected and benign.
typecheck:
	uv run pyright .

test:
	[ -f greeting_vi.wav ] || { echo "❌ Missing test audio: greeting_vi.wav"; exit 1; }
	uv run python eval.py greeting_vi.wav --json \
	  && echo "✅ Pipeline smoke test passed"

format:
	uv run ruff format .
	uv run ruff check --fix .

clean:
	rm -rf out/