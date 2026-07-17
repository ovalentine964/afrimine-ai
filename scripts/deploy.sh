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
DEPLOY_LOG=".deploy.log"
ROLLBACK_FILE=".deploy_rollback.json"

# ── Safe environment loading ─────────────────────────────
load_env() {
    local file="$1"
    if [ ! -f "$file" ]; then
        err "Environment file not found: $file"
    fi

    # Validate file permissions (should not be world-readable)
    local perms
    perms=$(stat -c %a "$file" 2>/dev/null || stat -f %Lp "$file" 2>/dev/null || echo "unknown")
    if [ "$perms" != "unknown" ] && [ "${perms: -1}" -ge 4 ]; then
        warn "Environment file $file is world-readable (perms: $perms). Consider: chmod 600 $file"
    fi

    # Source with validation — only allow KEY=VALUE lines, skip comments and empty lines
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        # Trim whitespace
        key=$(echo "$key" | xargs)
        # Validate key format (alphanumeric + underscore only)
        if [[ ! "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]]; then
            warn "Skipping invalid env var name: $key"
            continue
        fi
        # Remove surrounding quotes from value
        value=$(echo "$value" | sed 's/^["'\'']\(.*\)["'\'']$/\1/')
        export "$key=$value"
    done < "$file"
}

# ── Deploy state tracking ────────────────────────────────
track_deploy() {
    local target="$1"
    local status="$2"
    local version="${3:-unknown}"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "{\"target\":\"$target\",\"status\":\"$status\",\"version\":\"$version\",\"timestamp\":\"$timestamp\"}" >> "$DEPLOY_LOG"

    # Save rollback info
    if [ "$status" = "started" ]; then
        echo "{\"target\":\"$target\",\"version\":\"$version\",\"timestamp\":\"$timestamp\"}" > "$ROLLBACK_FILE"
    fi
}

# ── Rollback function ────────────────────────────────────
rollback() {
    local target="$1"
    warn "Initiating rollback for: $target"

    if [ ! -f "$ROLLBACK_FILE" ]; then
        warn "No rollback information found. Manual rollback required."
        echo "  1. Check Render dashboard for previous deploy"
        echo "  2. Redeploy from a known-good commit"
        return 1
    fi

    case "$target" in
        backend|ai-engine)
            warn "Render.com auto-deploy rollback:"
            echo "  1. Go to Render dashboard → $target service"
            echo "  2. Click 'Manual Deploy' → select previous commit"
            echo "  3. Or revert the git commit and push to trigger auto-deploy"
            ;;
        frontend)
            warn "Cloudflare Pages rollback:"
            echo "  1. Go to Cloudflare Pages → afrimine-ai project"
            echo "  2. Click 'Deployments' → find previous working deployment"
            echo "  3. Click '...' → 'Rollback to this deployment'"
            ;;
        db)
            warn "Database rollback requires manual intervention:"
            echo "  1. Check Supabase dashboard → SQL Editor"
            echo "  2. Run the DOWN migration if available"
            echo "  3. Restore from backup: scripts/backup.sh"
            ;;
    esac

    log "Rollback instructions provided for: $target"
}

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

load_env "$ENV_FILE"

# Get current git version for tracking
DEPLOY_VERSION=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
log "Deploying version: $DEPLOY_VERSION"

# ── Deploy Frontend (Cloudflare Pages) ───────────────────
deploy_frontend() {
    echo "── Deploying Frontend ──────────────────"
    track_deploy "frontend" "started" "$DEPLOY_VERSION"

    if ! command -v flutter &>/dev/null; then
        err "Flutter not found. Install Flutter to build the web app."
    fi

    cd src/frontend

    log "Building Flutter web..."
    flutter pub get
    if ! flutter build web --release \
        --dart-define=SUPABASE_URL="${SUPABASE_URL}" \
        --dart-define=SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY}" \
        --dart-define=API_BASE_URL="${API_BASE_URL:-https://api.afrimine.ai}"; then
        track_deploy "frontend" "failed" "$DEPLOY_VERSION"
        err "Flutter build failed"
    fi

    log "Build complete: $(du -sh build/web | cut -f1)"

    if command -v wrangler &>/dev/null; then
        log "Deploying to Cloudflare Pages..."
        if ! wrangler pages deploy build/web \
            --project-name="${CLOUDFLARE_PAGES_PROJECT:-afrimine-ai}" \
            --branch=main; then
            track_deploy "frontend" "failed" "$DEPLOY_VERSION"
            rollback "frontend"
            err "Frontend deployment failed"
        fi
        log "Frontend deployed to Cloudflare Pages"
    elif [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
        log "Installing wrangler..."
        npm install -g wrangler
        if ! wrangler pages deploy build/web \
            --project-name="${CLOUDFLARE_PAGES_PROJECT:-afrimine-ai}" \
            --branch=main; then
            track_deploy "frontend" "failed" "$DEPLOY_VERSION"
            rollback "frontend"
            err "Frontend deployment failed"
        fi
        log "Frontend deployed to Cloudflare Pages"
    else
        warn "No Cloudflare credentials found. Manual deploy needed:"
        echo "  1. Go to Cloudflare Pages dashboard"
        echo "  2. Upload build/web directory"
    fi

    track_deploy "frontend" "completed" "$DEPLOY_VERSION"
    cd ../..
}

# ── Deploy Backend (Render.com via deploy hook) ──────────
deploy_backend() {
    echo "── Deploying Backend ───────────────────"
    track_deploy "backend" "started" "$DEPLOY_VERSION"

    if [ -n "${RENDER_DEPLOY_HOOK_BACKEND:-}" ]; then
        log "Triggering Render deploy (backend)..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${RENDER_DEPLOY_HOOK_BACKEND}" || echo "000")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
            log "Backend deploy triggered (HTTP $HTTP_CODE)"
            track_deploy "backend" "triggered" "$DEPLOY_VERSION"
        else
            track_deploy "backend" "failed" "$DEPLOY_VERSION"
            rollback "backend"
            err "Render returned HTTP $HTTP_CODE — deploy hook failed"
        fi
    else
        warn "No Render deploy hook set. Add RENDER_DEPLOY_HOOK_BACKEND to $ENV_FILE"
        track_deploy "backend" "skipped" "$DEPLOY_VERSION"
    fi
}

# ── Deploy AI Engine (Render.com via deploy hook) ────────
deploy_ai_engine() {
    echo "── Deploying AI Engine ─────────────────"
    track_deploy "ai-engine" "started" "$DEPLOY_VERSION"

    if [ -n "${RENDER_DEPLOY_HOOK_AI_ENGINE:-}" ]; then
        log "Triggering Render deploy (AI engine)..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${RENDER_DEPLOY_HOOK_AI_ENGINE}" || echo "000")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
            log "AI engine deploy triggered (HTTP $HTTP_CODE)"
            track_deploy "ai-engine" "triggered" "$DEPLOY_VERSION"
        else
            track_deploy "ai-engine" "failed" "$DEPLOY_VERSION"
            rollback "ai-engine"
            err "Render returned HTTP $HTTP_CODE — deploy hook failed"
        fi
    else
        warn "No Render deploy hook set. Add RENDER_DEPLOY_HOOK_AI_ENGINE to $ENV_FILE"
        track_deploy "ai-engine" "skipped" "$DEPLOY_VERSION"
    fi
}

# ── Run Database Migrations ──────────────────────────────
deploy_db() {
    echo "── Running DB Migrations ───────────────"
    track_deploy "db" "started" "$DEPLOY_VERSION"

    if command -v supabase &>/dev/null; then
        log "Pushing migrations to Supabase..."
        if ! supabase db push; then
            track_deploy "db" "failed" "$DEPLOY_VERSION"
            rollback "db"
            err "Database migration failed"
        fi
        log "Database migrations applied"
        track_deploy "db" "completed" "$DEPLOY_VERSION"
    else
        warn "Supabase CLI not found. Install: npm i -g supabase"
        echo "  Or run migrations manually via Supabase dashboard SQL editor"
        track_deploy "db" "skipped" "$DEPLOY_VERSION"
    fi
}

# ── Health Check ─────────────────────────────────────────
health_check() {
    echo "── Health Check ────────────────────────"
    local url="${1:-https://api.afrimine.ai/health}"
    local retries=5
    local delay=10
    local timeout=15

    for i in $(seq 1 $retries); do
        local response
        local http_code
        response=$(curl -sf --max-time "$timeout" -w "\n%{http_code}" "$url" 2>/dev/null) || {
            warn "Attempt $i/$retries — service not ready, waiting ${delay}s..."
            sleep $delay
            continue
        }

        http_code=$(echo "$response" | tail -1)
        local body
        body=$(echo "$response" | head -n -1)

        if [ "$http_code" = "200" ]; then
            # Verify response contains expected health indicator
            if echo "$body" | grep -q '"healthy"' || echo "$body" | grep -q '"status"'; then
                log "Health check passed: $url"
                log "Response: $body"
                return 0
            else
                warn "Attempt $i/$retries — unexpected response body, waiting ${delay}s..."
            fi
        else
            warn "Attempt $i/$retries — HTTP $http_code, waiting ${delay}s..."
        fi
        sleep $delay
    done

    err "Health check failed after $retries attempts"
}

# ── Post-deploy validation ───────────────────────────────
validate_deploy() {
    echo "── Post-Deploy Validation ──────────────"
    local errors=0

    # Check backend health
    if ! health_check "https://api.afrimine.ai/health" 2>/dev/null; then
        warn "Backend health check failed"
        ((errors++))
    fi

    # Check AI engine health
    if ! health_check "https://api.afrimine.ai/ai/health" 2>/dev/null; then
        warn "AI engine health check failed"
        ((errors++))
    fi

    if [ "$errors" -gt 0 ]; then
        warn "$errors service(s) failed post-deploy validation"
        warn "Consider running: $0 rollback"
        return 1
    fi

    log "All services healthy post-deploy"
}

# ── Execute ──────────────────────────────────────────────
trap 'echo ""; warn "Deploy interrupted!"; exit 130' INT TERM

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
    rollback)
        if [ -n "${2:-}" ]; then
            rollback "$2"
        else
            echo "Usage: $0 rollback <target>"
            echo "Targets: frontend, backend, ai-engine, db"
            exit 1
        fi
        ;;
    all)
        deploy_db
        deploy_backend
        deploy_ai_engine
        deploy_frontend
        echo ""
        validate_deploy
        ;;
    *)
        err "Unknown target: $DEPLOY_TARGET. Use: all|frontend|backend|ai-engine|db|rollback"
        ;;
esac

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Deployment complete!"
echo "  Version: $DEPLOY_VERSION"
echo "═══════════════════════════════════════════"
