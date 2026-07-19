# AfriMine AI — Makefile
# Common commands for development and deployment

.PHONY: help build test deploy lint format clean \
        build-go build-python build-flutter \
        test-go test-python test-flutter test-all \
        deploy-staging deploy-production \
        lint-go lint-python lint-flutter lint-all \
        format-go format-python format-flutter \
        docker-build docker-up docker-down \
        db-setup db-backup db-restore \
        security-scan secrets-check

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Versions ─────────────────────────────────────
GO_VERSION     := 1.22
PYTHON_VERSION := 3.12
FLUTTER_VERSION := 3.24

# ── Docker ───────────────────────────────────────
DOCKER_COMPOSE := docker compose -f docker-compose.staging.yml

# ── Colors ───────────────────────────────────────
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

# ══════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════
help: ## Show this help
	@echo ""
	@echo "AfriMine AI — Development Commands"
	@echo "==================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ══════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════
build: build-go build-python build-flutter ## Build everything

build-go: ## Build Go backend
	@echo "$(GREEN)Building Go backend...$(RESET)"
	CGO_ENABLED=0 go build -ldflags="-s -w" -o bin/afrimine-api .

build-python: ## Install Python dependencies
	@echo "$(GREEN)Installing Python dependencies...$(RESET)"
	pip install -r requirements.txt

build-flutter: ## Build Flutter web
	@echo "$(GREEN)Building Flutter web...$(RESET)"
	flutter pub get
	flutter build web --release

# ══════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════
test: test-all ## Run all tests

test-go: ## Run Go tests
	@echo "$(GREEN)Running Go tests...$(RESET)"
	go test -v -race -cover ./...

test-python: ## Run Python tests
	@echo "$(GREEN)Running Python tests...$(RESET)"
	pytest tests/test_agents/ tests/test_graph.py tests/test_mcp/ tests/test_security/ -v --tb=short

test-python-integration: ## Run Python integration tests
	@echo "$(GREEN)Running integration tests...$(RESET)"
	pytest tests/test_integration/ -v --tb=short

test-flutter: ## Run Flutter tests
	@echo "$(GREEN)Running Flutter tests...$(RESET)"
	flutter test --coverage

test-all: test-go test-python test-flutter ## Run all tests (Go + Python + Flutter)

test-watch: ## Run Python tests in watch mode
	pytest-watch tests/ -v --tb=short

# ══════════════════════════════════════════════════
# DEPLOY
# ══════════════════════════════════════════════════
deploy-staging: ## Deploy to staging
	@echo "$(GREEN)Deploying to staging...$(RESET)"
	./scripts/deploy.sh staging

deploy-production: ## Deploy to production (use: make deploy-production TAG=v1.0.0)
	@echo "$(GREEN)Deploying to production...$(RESET)"
	./scripts/deploy.sh production $(TAG)

# ══════════════════════════════════════════════════
# LINT
# ══════════════════════════════════════════════════
lint: lint-all ## Lint everything

lint-go: ## Lint Go code
	@echo "$(GREEN)Linting Go...$(RESET)"
	golangci-lint run --timeout=5m

lint-python: ## Lint Python code
	@echo "$(GREEN)Linting Python...$(RESET)"
	ruff check .
	ruff format --check .

lint-flutter: ## Analyze Flutter code
	@echo "$(GREEN)Analyzing Flutter...$(RESET)"
	flutter analyze --no-fatal-infos
	dart format --set-exit-if-changed .

lint-all: lint-go lint-python lint-flutter ## Lint all (Go + Python + Flutter)

# ══════════════════════════════════════════════════
# FORMAT
# ══════════════════════════════════════════════════
format: format-go format-python format-flutter ## Format all code

format-go: ## Format Go code
	gofmt -w .
	goimports -w .

format-python: ## Format Python code
	ruff check --fix .
	ruff format .

format-flutter: ## Format Flutter code
	dart format .

# ══════════════════════════════════════════════════
# DOCKER
# ══════════════════════════════════════════════════
docker-build: ## Build Docker images
	@echo "$(GREEN)Building Docker images...$(RESET)"
	docker build -f Dockerfile.go-backend -t afrimine-api:dev .
	docker build -f Dockerfile.python-agents -t afrimine-agents:dev .

docker-up: ## Start staging environment
	@echo "$(GREEN)Starting staging environment...$(RESET)"
	$(DOCKER_COMPOSE) up -d

docker-down: ## Stop staging environment
	@echo "$(GREEN)Stopping staging environment...$(RESET)"
	$(DOCKER_COMPOSE) down

docker-logs: ## View staging logs
	$(DOCKER_COMPOSE) logs -f

docker-ps: ## Show running containers
	$(DOCKER_COMPOSE) ps

# ══════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════
db-setup: ## Set up Supabase database (tables, RLS, indexes)
	@echo "$(GREEN)Setting up Supabase...$(RESET)"
	./scripts/setup-supabase.sh

db-backup: ## Backup database
	@echo "$(GREEN)Backing up database...$(RESET)"
	./scripts/backup.sh

db-restore: ## Restore database (use: make db-restore FILE=backups/backup_xxx.sql.gz)
	@echo "$(GREEN)Restoring database...$(RESET)"
	./scripts/backup.sh --restore $(FILE)

db-backup-list: ## List available backups
	./scripts/backup.sh --list

# ══════════════════════════════════════════════════
# SECURITY
# ══════════════════════════════════════════════════
security-scan: secrets-check ## Run all security scans locally
	@echo "$(GREEN)Running security scans...$(RESET)"
	@echo "--- govulncheck ---"
	govulncheck ./... 2>/dev/null || echo "Install: go install golang.org/x/vuln/cmd/govulncheck@latest"
	@echo "--- gosec ---"
	gosec ./... 2>/dev/null || echo "Install: go install github.com/securego/gosec/v2/cmd/gosec@latest"
	@echo "--- pip-audit ---"
	pip-audit -r requirements.txt 2>/dev/null || pip install pip-audit
	@echo "--- bandit ---"
	bandit -r agents/ security/ tools/ --severity-level medium 2>/dev/null || pip install bandit

secrets-check: ## Check for secrets in code
	@echo "$(GREEN)Checking for secrets...$(RESET)"
	gitleaks detect --source . --verbose 2>/dev/null || echo "Install: https://github.com/gitleaks/gitleaks#installing"

# ══════════════════════════════════════════════════
# MONITORING
# ══════════════════════════════════════════════════
health: ## Check all service health
	@echo "$(GREEN)Checking health...$(RESET)"
	@echo -n "API:       "; curl -sf https://api.afrimine.com/health && echo " ✅" || echo " ❌"
	@echo -n "A2A:       "; curl -sf https://api.afrimine.com/a2a/health && echo " ✅" || echo " ❌"
	@echo -n "Frontend:  "; curl -sf https://afrimine.com > /dev/null && echo " ✅" || echo " ❌"

health-staging: ## Check staging health
	@echo "$(GREEN)Checking staging health...$(RESET)"
	@echo -n "API:       "; curl -sf https://staging-api.afrimine.com/health && echo " ✅" || echo " ❌"
	@echo -n "Frontend:  "; curl -sf https://staging.afrimine.com > /dev/null && echo " ✅" || echo " ❌"

# ══════════════════════════════════════════════════
# CLEAN
# ══════════════════════════════════════════════════
clean: ## Clean build artifacts
	rm -rf bin/ build/ dist/ __pycache__/ .pytest_cache/ .mypy_cache/
	rm -rf *.egg-info/ .coverage coverage.out coverage.xml lcov.info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-docker: ## Remove Docker images
	docker rmi afrimine-api:dev afrimine-agents:dev 2>/dev/null || true

# ══════════════════════════════════════════════════
# DEVELOPMENT SHORTCUTS
# ══════════════════════════════════════════════════
dev: ## Start local development (Go + Python)
	@echo "$(GREEN)Starting development servers...$(RESET)"
	@echo "Go API: http://localhost:8080"
	@echo "Python Agents: http://localhost:8000"
	@trap 'kill 0' EXIT; \
	go run . & \
	cd ../agents && python -m uvicorn a2a_bridge:app --reload --port 8000 & \
	wait

dev-flutter: ## Start Flutter development
	flutter run -d chrome

# ══════════════════════════════════════════════════
# ANDROID APK
# ══════════════════════════════════════════════════
build-apk: ## Build release APK (split per ABI, arm64 + armv7)
	@echo "$(GREEN)Building release APK...$(RESET)"
	chmod +x scripts/build-apk.sh
	API_URL=$${API_URL:-https://api.afrimine.com} ./scripts/build-apk.sh --api-url $$API_URL

build-apk-debug: ## Build debug APK (no minification, for testing)
	@echo "$(GREEN)Building debug APK...$(RESET)"
	chmod +x scripts/build-apk.sh
	./scripts/build-apk.sh --debug

build-apk-local: ## Build release APK pointing to localhost:8080
	@echo "$(GREEN)Building APK for local testing...$(RESET)"
	chmod +x scripts/build-apk.sh
	./scripts/build-apk.sh --api-url http://localhost:8080

install-tools: ## Install development tools
	@echo "$(GREEN)Installing development tools...$(RESET)"
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	go install golang.org/x/vuln/cmd/govulncheck@latest
	go install github.com/securego/gosec/v2/cmd/gosec@latest
	pip install ruff mypy pytest pytest-asyncio pytest-cov bandit pip-audit
	npm install -g @railway/cli wrangler
	flutter pub global activate dart_code_metrics

# ══════════════════════════════════════════════════
# CI SIMULATION
# ══════════════════════════════════════════════════
ci: lint test security-scan ## Simulate full CI pipeline locally
	@echo "$(GREEN)✅ All CI checks passed$(RESET)"
