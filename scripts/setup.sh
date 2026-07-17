#!/usr/bin/env bash
# AfriMine AI — Initial Setup Script
# Run once to set up local development environment
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo "═══════════════════════════════════════════"
echo "  AfriMine AI — Development Setup"
echo "═══════════════════════════════════════════"
echo ""

# ── Check prerequisites ──────────────────────────────────
check_tool() {
    if ! command -v "$1" &>/dev/null; then
        err "$1 is required but not installed. $2"
    fi
    log "$1 found: $(command -v "$1")"
}

check_tool docker "Install from https://docs.docker.com/get-docker/"
check_tool git    "Install from https://git-scm.com/"

# Optional tools
command -v go     &>/dev/null && log "Go found: $(go version)"     || warn "Go not found (needed for local backend dev)"
command -v python3 &>/dev/null && log "Python found: $(python3 --version)" || warn "Python 3.11+ not found (needed for AI engine dev)"
command -v flutter &>/dev/null && log "Flutter found: $(flutter --version | head -1)" || warn "Flutter not found (needed for frontend dev)"
command -v supabase &>/dev/null && log "Supabase CLI found" || warn "Supabase CLI not found (install: npm i -g supabase)"

# ── Create .env from example ─────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    log "Created .env from .env.example"
    warn "Edit .env and fill in your API keys before running"
else
    warn ".env already exists, skipping"
fi

# ── Create directories ───────────────────────────────────
mkdir -p data/{raw,processed}
mkdir -p logs
mkdir -p docker/nginx/ssl
log "Created data and log directories"

# ── Generate self-signed SSL cert for local dev ──────────
if [ ! -f docker/nginx/ssl/privkey.pem ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout docker/nginx/ssl/privkey.pem \
        -out docker/nginx/ssl/fullchain.pem \
        -subj "/C=KE/ST=Nairobi/L=Nairobi/O=AfriMine/OU=Dev/CN=localhost" \
        2>/dev/null
    log "Generated self-signed SSL certificate for local dev"
else
    warn "SSL cert already exists, skipping"
fi

# ── Start Docker services ────────────────────────────────
echo ""
echo "Starting Docker services..."
docker compose up -d db redis
log "Database and Redis started"

# Wait for DB
echo "Waiting for database to be ready..."
for i in {1..30}; do
    if docker compose exec -T db pg_isready -U afrimine -d afrimine &>/dev/null; then
        log "Database is ready"
        break
    fi
    sleep 1
done

# ── Run migrations ───────────────────────────────────────
echo ""
echo "Running database migrations..."
for f in supabase/migrations/*.sql; do
    docker compose exec -T db psql -U afrimine -d afrimine -f "/docker-entrypoint-initdb.d/$(basename "$f")" 2>/dev/null && \
        log "Applied: $(basename "$f")" || \
        warn "Skipped (already applied): $(basename "$f")"
done

# ── Install Go dependencies ──────────────────────────────
if command -v go &>/dev/null; then
    echo ""
    echo "Installing Go dependencies..."
    cd src/backend && go mod download && cd ../..
    log "Go dependencies installed"
fi

# ── Install Python dependencies ──────────────────────────
if command -v python3 &>/dev/null; then
    echo ""
    echo "Setting up Python virtual environment..."
    cd src/ai-engine
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate
    cd ../..
    log "Python dependencies installed in venv"
fi

# ── Install Flutter dependencies ─────────────────────────
if command -v flutter &>/dev/null; then
    echo ""
    echo "Installing Flutter dependencies..."
    cd src/frontend && flutter pub get && cd ../..
    log "Flutter dependencies installed"
fi

# ── Done ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Run: docker compose up --build"
echo "  3. Open: http://localhost:8080/health"
echo "═══════════════════════════════════════════"
