#!/usr/bin/env bash
# AfriMine AI — Database Backup Script
# Backs up Supabase PostgreSQL to local file
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Configuration ────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/afrimine_${TIMESTAMP}.sql.gz"
ENV_FILE="${1:-.env.production}"

mkdir -p "$BACKUP_DIR"

# ── Load env ─────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    warn "No env file found: $ENV_FILE"
fi

# ── Backup via Supabase CLI ──────────────────────────────
backup_supabase_cli() {
    log "Using Supabase CLI for backup..."
    supabase db dump --file "$BACKUP_DIR/afrimine_${TIMESTAMP}.sql"
    gzip "$BACKUP_DIR/afrimine_${TIMESTAMP}.sql"
    log "Backup saved: ${BACKUP_FILE}"
}

# ── Backup via pg_dump ───────────────────────────────────
backup_pg_dump() {
    log "Using pg_dump for backup..."
    local db_url="${DATABASE_URL:?DATABASE_URL is required}"

    pg_dump "$db_url" \
        --format=custom \
        --compress=9 \
        --verbose \
        --no-owner \
        --no-privileges \
        --file="${BACKUP_DIR}/afrimine_${TIMESTAMP}.dump" 2>/dev/null

    # Also SQL dump for portability
    pg_dump "$db_url" \
        --format=plain \
        --no-owner \
        --no-privileges \
        | gzip > "$BACKUP_FILE"

    log "Backup saved: ${BACKUP_FILE}"
    log "Dump file: ${BACKUP_DIR}/afrimine_${TIMESTAMP}.dump"
}

# ── Backup via Docker ────────────────────────────────────
backup_docker() {
    log "Using Docker for backup..."
    docker compose exec -T db pg_dump \
        -U afrimine \
        -d afrimine \
        --format=plain \
        --no-owner \
        --no-privileges \
        | gzip > "$BACKUP_FILE"

    log "Backup saved: ${BACKUP_FILE}"
}

# ── Cleanup old backups ──────────────────────────────────
cleanup_old_backups() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days..."
    local count
    count=$(find "$BACKUP_DIR" -name "afrimine_*.sql.gz" -mtime "+${RETENTION_DAYS}" | wc -l)
    find "$BACKUP_DIR" -name "afrimine_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
    find "$BACKUP_DIR" -name "afrimine_*.dump" -mtime "+${RETENTION_DAYS}" -delete
    log "Removed $count old backup(s)"
}

# ── Verify backup ────────────────────────────────────────
verify_backup() {
    if [ -f "$BACKUP_FILE" ]; then
        local size
        size=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup verified: $size"

        # Check it's valid gzip
        if gzip -t "$BACKUP_FILE" 2>/dev/null; then
            log "Gzip integrity check passed"
        else
            err "Backup file is corrupted!"
        fi
    else
        err "Backup file not found!"
    fi
}

# ── Execute ──────────────────────────────────────────────
echo "═══════════════════════════════════════════"
echo "  AfriMine AI — Database Backup"
echo "  $(date)"
echo "═══════════════════════════════════════════"
echo ""

# Choose backup method
if command -v supabase &>/dev/null && [ -n "${SUPABASE_PROJECT_REF:-}" ]; then
    backup_supabase_cli
elif [ -n "${DATABASE_URL:-}" ]; then
    backup_pg_dump
elif docker compose ps db &>/dev/null 2>&1; then
    backup_docker
else
    err "No backup method available. Set DATABASE_URL or ensure Docker is running."
fi

verify_backup
cleanup_old_backups

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Backup complete!"
echo "  File: ${BACKUP_FILE}"
echo "═══════════════════════════════════════════"
