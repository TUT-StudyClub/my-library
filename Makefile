.PHONY: lint format format-check typecheck

lint:
	@echo "== Frontend lint =="
	cd frontend && npm run lint
	@echo "== Backend lint =="
	cd backend && uv sync --extra dev
	cd backend && uv run ruff check .

format:
	@echo "== Frontend format =="
	cd frontend && npm run format
	@echo "== Backend format =="
	cd backend && uv sync --extra dev
	cd backend && uv run black .

format-check:
	@echo "== Frontend format-check =="
	cd frontend && npm run format:check
	@echo "== Backend format-check =="
	cd backend && uv sync --extra dev
	cd backend && uv run black --check .

typecheck:
	@echo "== Frontend typecheck =="
	cd frontend && npm run typecheck
	@echo "== Backend typecheck =="
	cd backend && uv sync --extra dev
	cd backend && uv run mypy src/main.py
