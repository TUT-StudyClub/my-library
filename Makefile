.PHONY: check check-all check-frontend check-backend frontend-setup frontend-run backend-setup backend-run dev db-smoke lint format format-check typecheck test

FRONTEND_DIR := frontend
BACKEND_DIR := backend

check:
	@echo "== Detect changed files =="
	@changedFiles="$$( (git diff --name-only HEAD; git ls-files --others --exclude-standard) | sort -u )"; \
	if [ -z "$$changedFiles" ]; then \
		echo "変更ファイルがないため、フルチェックを実行します。"; \
		$(MAKE) check-all; \
		exit $$?; \
	fi; \
	frontendChanged=0; \
	backendChanged=0; \
	sharedChanged=0; \
	if printf '%s\n' "$$changedFiles" | grep -Eq '^frontend/'; then frontendChanged=1; fi; \
	if printf '%s\n' "$$changedFiles" | grep -Eq '^backend/'; then backendChanged=1; fi; \
	if printf '%s\n' "$$changedFiles" | grep -Eq '^(Makefile|\.github/workflows/ci\.yml)$$'; then sharedChanged=1; fi; \
	if [ "$$sharedChanged" -eq 1 ]; then \
		frontendChanged=1; \
		backendChanged=1; \
	fi; \
	if [ "$$frontendChanged" -eq 0 ] && [ "$$backendChanged" -eq 0 ]; then \
		echo "docs/README などの変更のみのため、check をスキップします。"; \
		exit 0; \
	fi; \
	if [ "$$frontendChanged" -eq 1 ]; then \
		$(MAKE) check-frontend || exit $$?; \
	fi; \
	if [ "$$backendChanged" -eq 1 ]; then \
		$(MAKE) check-backend || exit $$?; \
	fi

check-all: lint format-check typecheck test

check-frontend:
	@echo "== Frontend check =="
	cd $(FRONTEND_DIR) && npm run lint
	cd $(FRONTEND_DIR) && npm run format:check
	cd $(FRONTEND_DIR) && npm run typecheck

check-backend: backend-setup
	@echo "== Backend check =="
	cd $(BACKEND_DIR) && uv run ruff check .
	cd $(BACKEND_DIR) && uv run black --check .
	cd $(BACKEND_DIR) && uv run mypy src
	cd $(BACKEND_DIR) && uv run pytest -q

frontend-setup:
	@echo "== Frontend setup =="
	cd $(FRONTEND_DIR) && npm install

frontend-run: frontend-setup
	@echo "== Frontend app start =="
	cd $(FRONTEND_DIR) && npm run dev

backend-setup:
	@echo "== Backend setup =="
	cd $(BACKEND_DIR) && uv sync --extra dev

db-smoke: backend-setup
	@echo "== Backend register->fetch smoke =="
	cd $(BACKEND_DIR) && uv run python -m src.db_smoke --log-path data/register_fetch_result.json

backend-run: backend-setup
	@echo "== Backend API start =="
	cd $(BACKEND_DIR) && uv run python -m src

dev:
	@echo "== Frontend + Backend start (Ctrl+C で終了) =="
	$(MAKE) -j2 frontend-run backend-run

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
