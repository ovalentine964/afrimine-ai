#!/usr/bin/env bash
# AfriMine AI — One-Command Deployment
# Usage:
#   ./scripts/deploy.sh staging     # Deploy to staging
#   ./scripts/deploy.sh production  # Deploy to production (requires tag)
#   ./scripts/deploy.sh production v1.0.0  # Deploy specific tag to production

set -euo pipefail

# ── Colors ───────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }
info()  { echo -e "${BLUE}[info]${NC} $*"; }

# ── Parse Arguments ──────────────────────────────
ENV="${1:-}"
TAG="${2:-}"

if [[ -z "$ENV" ]] || [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
    error "Usage: ./scripts/deploy.sh <staging|production> [tag]"
    error ""
    error "  staging              Deploy current branch to staging"
    error "  production           Deploy current HEAD to production"
    error "  production v1.0.0    Deploy specific tag to production"
    exit 1
fi

# ── Preflight Checks ────────────────────────────
log "Running preflight checks..."

# Check required tools
for cmd in git docker curl; do
    if ! command -v "$cmd" &>/dev/null; then
        error "Required tool not found: $cmd"
        exit 1
    fi
done

# Check Railway CLI
if ! command -v railway &>/dev/null; then
    warn "Railway CLI not found. Installing..."
    npm install -g @railway/cli 2>/dev/null || {
        error "Failed to install Railway CLI. Install manually: npm install -g @railway/cli"
        exit 1
    }
fi

# Check Wrangler CLI
if ! command -v wrangler &>/dev/null; then
    warn "Wrangler CLI not found. Installing..."
    npm install -g wrangler 2>/dev/null || {
        error "Failed to install Wrangler. Install manually: npm install -g wrangler"
        exit 1
    }
fi

# Check git status
if [[ -n "$(git status --porcelain)" ]]; then
    warn "Working directory has uncommitted changes."
    if [[ "$ENV" == "production" ]]; then
        error "Cannot deploy to production with uncommitted changes. Commit first."
        exit 1
    fi
    read -rp "Continue with uncommitted changes? (y/N) " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 0
fi

# ── Environment Configuration ───────────────────
if [[ "$ENV" == "staging" ]]; then
    RAILWAY_PROJECT="afrimine-staging"
    RAILWAY_SERVICE_API="go-api-staging"
    RAILWAY_SERVICE_AGENTS="langgraph-staging"
    CF_PAGES_PROJECT="afrimine-web"
    CF_BRANCH="staging"
    API_URL="https://staging-api.afrimine.com"
    FRONTEND_URL="https://staging.afrimine.com"
    DEPLOY_TAG=$(git rev-parse --short HEAD)
else
    RAILWAY_PROJECT="afrimine-production"
    RAILWAY_SERVICE_API="go-api"
    RAILWAY_SERVICE_AGENTS="langgraph"
    CF_PAGES_PROJECT="afrimine-web"
    CF_BRANCH="main"
    API_URL="https://api.afrimine.com"
    FRONTEND_URL="https://afrimine.com"
    DEPLOY_TAG="${TAG:-$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)}"
fi

log "Deploying to ${ENV} (tag: ${DEPLOY_TAG})"

# ── Step 1: Build Flutter Web ───────────────────
log "Step 1/5: Building Flutter Web..."

if command -v flutter &>/dev/null; then
    flutter pub get
    flutter build web --release \
        --dart-define=ENV="${ENV}" \
        --dart-define=API_URL="${API_URL}" \
        --dart-define=VERSION="${DEPLOY_TAG}"
    FLUTTER_BUILD_DIR="build/web"
else
    warn "Flutter not found locally. Using Docker for build..."
    docker run --rm -v "$(pwd)":/app -w /app \
        ghcr.io/cirruslabs/flutter:stable \
        sh -c "flutter pub get && flutter build web --release --dart-define=ENV=${ENV} --dart-define=API_URL=${API_URL}"
    FLUTTER_BUILD_DIR="build/web"
fi

log "  ✅ Flutter build complete"

# ── Step 2: Build Docker Images ─────────────────
log "Step 2/5: Building Docker images..."

docker build -f Dockerfile.go-backend \
    -t "afrimine-api:${DEPLOY_TAG}" \
    --build-arg VERSION="${DEPLOY_TAG}" \
    . 2>&1 | tail -3

docker build -f Dockerfile.python-agents \
    -t "afrimine-agents:${DEPLOY_TAG}" \
    . 2>&1 | tail -3

log "  ✅ Docker images built"

# ── Step 3: Deploy Frontend to Cloudflare Pages ──
log "Step 3/5: Deploying frontend to Cloudflare Pages..."

if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    wrangler pages deploy "${FLUTTER_BUILD_DIR}" \
        --project-name="${CF_PAGES_PROJECT}" \
        --branch="${CF_BRANCH}" \
        --commit-hash="$(git rev-parse HEAD)" 2>&1 | tail -3
    log "  ✅ Frontend deployed to ${FRONTEND_URL}"
else
    warn "CLOUDFLARE_API_TOKEN not set. Skipping frontend deploy."
    warn "Set it in your environment or GitHub Secrets."
fi

# ── Step 4: Deploy Backend to Railway ────────────
log "Step 4/5: Deploying backend to Railway..."

if [[ -n "${RAILWAY_TOKEN:-}" ]]; then
    railway link --project "${RAILWAY_PROJECT}"

    # Deploy Go API
    log "  → Deploying Go API..."
    railway up --service "${RAILWAY_SERVICE_API}" 2>&1 | tail -3

    # Deploy Python Agents
    log "  → Deploying Python LangGraph agents..."
    railway up --service "${RAILWAY_SERVICE_AGENTS}" 2>&1 | tail -3

    log "  ✅ Backend deployed"
else
    warn "RAILWAY_TOKEN not set. Skipping Railway deploy."
    warn "Set it in your environment or GitHub Secrets."
fi

# ── Step 5: Health Verification ──────────────────
log "Step 5/5: Verifying deployment..."

sleep 10  # Give services time to start

HEALTH_OK=true

# Check API
for i in {1..6}; do
    if curl -sf "${API_URL}/health" > /dev/null 2>&1; then
        log "  ✅ API health: OK"
        break
    fi
    if [[ $i -eq 6 ]]; then
        warn "  ⚠️  API health check failed after 6 attempts"
        HEALTH_OK=false
    fi
    sleep 10
done

# Check A2A
if curl -sf "${API_URL}/a2a/health" > /dev/null 2>&1; then
    log "  ✅ A2A health: OK"
else
    warn "  ⚠️  A2A health check failed"
    HEALTH_OK=false
fi

# Check Frontend
if curl -sf "${FRONTEND_URL}" > /dev/null 2>&1; then
    log "  ✅ Frontend: OK"
else
    warn "  ⚠️  Frontend check failed"
    HEALTH_OK=false
fi

# ── Summary ──────────────────────────────────────
echo ""
log "══════════════════════════════════════════════"
log "  Deployment Summary"
log "══════════════════════════════════════════════"
log "  Environment:  ${ENV}"
log "  Tag:          ${DEPLOY_TAG}"
log "  Frontend:     ${FRONTEND_URL}"
log "  API:          ${API_URL}"
log "  A2A:          ${API_URL}/a2a"
log "══════════════════════════════════════════════"

if [[ "$HEALTH_OK" == "true" ]]; then
    log "  Status:       ✅ All services healthy"
    exit 0
else
    warn "  Status:       ⚠️  Some checks failed — verify manually"
    exit 1
fi
