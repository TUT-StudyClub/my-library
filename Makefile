.PHONY: check backend-setup db-smoke lint format format-check typecheck test

FRONTEND_DIR := frontend
BACKEND_DIR := backend

check: lint format-check typecheck test

backend-setup:
	@echo "== Backend setup =="
	cd $(BACKEND_DIR) && uv sync --extra dev

db-smoke: backend-setup
	@echo "== Backend register->fetch smoke =="
	cd $(BACKEND_DIR) && uv run python -m src.db_smoke --log-path data/register_fetch_result.json

lint: backend-setup
	@echo "== Frontend lint =="
	cd $(FRONTEND_DIR) && npm run lint
	@echo "== Backend lint =="
	cd $(BACKEND_DIR) && uv run ruff check .

format: backend-setup
	@echo "== Frontend format =="
	cd $(FRONTEND_DIR) && npm run format
	@echo "== Backend format =="
	cd $(BACKEND_DIR) && uv run black .

format-check: backend-setup
	@echo "== Frontend format-check =="
	cd $(FRONTEND_DIR) && npm run format:check
	@echo "== Backend format-check =="
	cd $(BACKEND_DIR) && uv run black --check .

typecheck: backend-setup
	@echo "== Frontend typecheck =="
	cd $(FRONTEND_DIR) && npm run typecheck
	@echo "== Backend typecheck =="
	cd $(BACKEND_DIR) && uv run mypy src

test: backend-setup
	@echo "== Backend test =="
	cd $(BACKEND_DIR) && uv run pytest -q
