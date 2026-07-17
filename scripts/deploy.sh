#!/usr/bin/env bash
# AfriMine AI — Deployment Script
# Deploys to production (Render + Cloudflare Pages)
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Configuration ────────────────────────────────────────
DEPLOY_TARGET="${1:-all}"   # all | frontend | backend | ai-engine | db
ENV_FILE="${2:-.env.production}"

if [ ! -f "$ENV_FILE" ]; then
    err "Environment file not found: $ENV_FILE"
fi

echo "═══════════════════════════════════════════"
echo "  AfriMine AI — Production Deploy"
echo "  Target: $DEPLOY_TARGET"
echo "═══════════════════════════════════════════"
echo ""

# ── Pre-flight checks ───────────────────────────────────
check_env() {
    local var="$1"
    if [ -z "${!var:-}" ]; then
        err "Missing required env var: $var"
    fi
}

source "$ENV_FILE"

# ── Deploy Frontend (Cloudflare Pages) ───────────────────
deploy_frontend() {
    echo "── Deploying Frontend ──────────────────"

    if ! command -v flutter &>/dev/null; then
        err "Flutter not found. Install Flutter to build the web app."
    fi

    cd src/frontend

    log "Building Flutter web..."
    flutter pub get
    flutter build web --release \
        --dart-define=SUPABASE_URL="${SUPABASE_URL}" \
        --dart-define=SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY}" \
        --dart-define=API_BASE_URL="${API_BASE_URL:-https://api.afrimine.ai}"

    log "Build complete: $(du -sh build/web | cut -f1)"

    if command -v wrangler &>/dev/null; then
        log "Deploying to Cloudflare Pages..."
        wrangler pages deploy build/web \
            --project-name="${CLOUDFLARE_PAGES_PROJECT:-afrimine-ai}" \
            --branch=main
        log "Frontend deployed to Cloudflare Pages"
    elif [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
        log "Installing wrangler..."
        npm install -g wrangler
        wrangler pages deploy build/web \
            --project-name="${CLOUDFLARE_PAGES_PROJECT:-afrimine-ai}" \
            --branch=main
        log "Frontend deployed to Cloudflare Pages"
    else
        warn "No Cloudflare credentials found. Manual deploy needed:"
        echo "  1. Go to Cloudflare Pages dashboard"
        echo "  2. Upload build/web directory"
    fi

    cd ../..
}

# ── Deploy Backend (Render.com via deploy hook) ──────────
deploy_backend() {
    echo "── Deploying Backend ───────────────────"

    if [ -n "${RENDER_DEPLOY_HOOK_BACKEND:-}" ]; then
        log "Triggering Render deploy (backend)..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${RENDER_DEPLOY_HOOK_BACKEND}")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
            log "Backend deploy triggered (HTTP $HTTP_CODE)"
        else
            warn "Render returned HTTP $HTTP_CODE — check dashboard"
        fi
    else
        warn "No Render deploy hook set. Add RENDER_DEPLOY_HOOK_BACKEND to $ENV_FILE"
    fi
}

# ── Deploy AI Engine (Render.com via deploy hook) ────────
deploy_ai_engine() {
    echo "── Deploying AI Engine ─────────────────"

    if [ -n "${RENDER_DEPLOY_HOOK_AI_ENGINE:-}" ]; then
        log "Triggering Render deploy (AI engine)..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${RENDER_DEPLOY_HOOK_AI_ENGINE}")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
            log "AI engine deploy triggered (HTTP $HTTP_CODE)"
        else
            warn "Render returned HTTP $HTTP_CODE — check dashboard"
        fi
    else
        warn "No Render deploy hook set. Add RENDER_DEPLOY_HOOK_AI_ENGINE to $ENV_FILE"
    fi
}

# ── Run Database Migrations ──────────────────────────────
deploy_db() {
    echo "── Running DB Migrations ───────────────"

    if command -v supabase &>/dev/null; then
        log "Pushing migrations to Supabase..."
        supabase db push
        log "Database migrations applied"
    else
        warn "Supabase CLI not found. Install: npm i -g supabase"
        echo "  Or run migrations manually via Supabase dashboard SQL editor"
    fi
}

# ── Health Check ─────────────────────────────────────────
health_check() {
    echo "── Health Check ────────────────────────"
    local url="${1:-https://api.afrimine.ai/health}"
    local retries=5
    local delay=10

    for i in $(seq 1 $retries); do
        if curl -sf "$url" > /dev/null 2>&1; then
            log "Health check passed: $url"
            return 0
        fi
        warn "Attempt $i/$retries — waiting ${delay}s..."
        sleep $delay
    done

    err "Health check failed after $retries attempts"
}

# ── Execute ──────────────────────────────────────────────
case "$DEPLOY_TARGET" in
    frontend)
        deploy_frontend
        ;;
    backend)
        deploy_backend
        ;;
    ai-engine)
        deploy_ai_engine
        ;;
    db)
        deploy_db
        ;;
    all)
        deploy_db
        deploy_backend
        deploy_ai_engine
        deploy_frontend
        echo ""
        health_check "https://api.afrimine.ai/health"
        ;;
    *)
        err "Unknown target: $DEPLOY_TARGET. Use: all|frontend|backend|ai-engine|db"
        ;;
esac

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo "═══════════════════════════════════════════"
