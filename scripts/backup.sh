#!/usr/bin/env bash
# AfriMine AI — Database Backup Script
# Backs up Supabase PostgreSQL to local file + optional S3 upload
# Usage:
#   ./scripts/backup.sh                  # Full backup
#   ./scripts/backup.sh --tables analyses,mineral_samples  # Specific tables
#   ./scripts/backup.sh --restore backup_20260719.sql.gz   # Restore

set -euo pipefail

# ── Configuration ────────────────────────────────
: "${SUPABASE_DB_HOST:?Set SUPABASE_DB_HOST}"
: "${SUPABASE_DB_PASSWORD:?Set SUPABASE_DB_PASSWORD}"

DB_HOST="${SUPABASE_DB_HOST}"
DB_PORT="${SUPABASE_DB_PORT:-5432}"
DB_NAME="${SUPABASE_DB_NAME:-postgres}"
DB_USER="${SUPABASE_DB_USER:-postgres}"
DB_URL="postgresql://${DB_USER}:${SUPABASE_DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ── Colors ───────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[backup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

# ── Parse Arguments ──────────────────────────────
MODE="backup"
TABLES=""
RESTORE_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tables)
            TABLES="$2"
            shift 2
            ;;
        --restore)
            MODE="restore"
            RESTORE_FILE="$2"
            shift 2
            ;;
        --list)
            MODE="list"
            shift
            ;;
        --help)
            echo "Usage:"
            echo "  ./scripts/backup.sh                           # Full backup"
            echo "  ./scripts/backup.sh --tables t1,t2            # Specific tables"
            echo "  ./scripts/backup.sh --restore file.sql.gz     # Restore"
            echo "  ./scripts/backup.sh --list                    # List backups"
            exit 0
            ;;
        *)
            error "Unknown argument: $1"
            exit 1
            ;;
    esac
done

mkdir -p "${BACKUP_DIR}"

# ── List Mode ────────────────────────────────────
if [[ "$MODE" == "list" ]]; then
    log "Available backups in ${BACKUP_DIR}:"
    ls -lh "${BACKUP_DIR}"/backup_*.sql.gz 2>/dev/null || warn "No backups found"
    exit 0
fi

# ── Restore Mode ─────────────────────────────────
if [[ "$MODE" == "restore" ]]; then
    if [[ ! -f "${RESTORE_FILE}" ]]; then
        error "Backup file not found: ${RESTORE_FILE}"
        exit 1
    fi

    log "⚠️  WARNING: This will overwrite the database!"
    log "  File: ${RESTORE_FILE}"
    log "  Target: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
    read -rp "Type 'RESTORE' to confirm: " confirm
    [[ "$confirm" == "RESTORE" ]] || { error "Aborted."; exit 1; }

    log "Restoring from ${RESTORE_FILE}..."

    if [[ "${RESTORE_FILE}" == *.gz ]]; then
        gunzip -c "${RESTORE_FILE}" | psql "${DB_URL}" 2>&1 | tail -5
    else
        psql "${DB_URL}" -f "${RESTORE_FILE}" 2>&1 | tail -5
    fi

    log "✅ Restore complete"
    exit 0
fi

# ── Backup Mode ──────────────────────────────────
log "Starting backup..."
log "  Host: ${DB_HOST}"
log "  Database: ${DB_NAME}"

BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"
METADATA_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.meta.json"

# Build pg_dump command
PG_DUMP_CMD="pg_dump '${DB_URL}' --no-owner --no-acl --if-exists --clean"

if [[ -n "$TABLES" ]]; then
    log "  Tables: ${TABLES}"
    IFS=',' read -ra TABLE_ARRAY <<< "$TABLES"
    for table in "${TABLE_ARRAY[@]}"; do
        PG_DUMP_CMD+=" --table=${table}"
    done
    BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}_partial.sql.gz"
else
    log "  Mode: Full backup"
fi

# Run backup
log "Dumping database..."
eval "${PG_DUMP_CMD}" 2>/dev/null | gzip > "${BACKUP_FILE}"

# Verify backup
BACKUP_SIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat -c%s "${BACKUP_FILE}" 2>/dev/null)
BACKUP_SIZE_MB=$(echo "scale=2; ${BACKUP_SIZE} / 1048576" | bc)

if [[ "${BACKUP_SIZE}" -lt 100 ]]; then
    error "Backup file suspiciously small (${BACKUP_SIZE} bytes). Check database connection."
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Write metadata
cat > "${METADATA_FILE}" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "host": "${DB_HOST}",
    "database": "${DB_NAME}",
    "tables": "${TABLES:-all}",
    "file": "${BACKUP_FILE}",
    "size_bytes": ${BACKUP_SIZE},
    "size_human": "${BACKUP_SIZE_MB}MB",
    "checksum": "$(sha256sum "${BACKUP_FILE}" | cut -d' ' -f1)"
}
EOF

log "✅ Backup complete"
log "  File: ${BACKUP_FILE}"
log "  Size: ${BACKUP_SIZE_MB}MB"

# ── Upload to S3 (optional) ─────────────────────
if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
    if command -v aws &>/dev/null; then
        log "Uploading to S3: ${BACKUP_S3_BUCKET}"
        aws s3 cp "${BACKUP_FILE}" "s3://${BACKUP_S3_BUCKET}/backups/" \
            --storage-class STANDARD_IA 2>&1 | tail -1
        aws s3 cp "${METADATA_FILE}" "s3://${BACKUP_S3_BUCKET}/backups/" 2>&1 | tail -1
        log "  ✅ Uploaded to S3"
    else
        warn "AWS CLI not found. Skipping S3 upload."
    fi
fi

# ── Upload to Supabase Storage (optional) ────────
if [[ -n "${SUPABASE_URL:-}" && -n "${SUPABASE_SERVICE_KEY:-}" ]]; then
    log "Uploading to Supabase Storage..."
    curl -sf -X POST \
        "${SUPABASE_URL}/storage/v1/object/backups/backup_${TIMESTAMP}.sql.gz" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
        -H "Content-Type: application/gzip" \
        --data-binary "@${BACKUP_FILE}" > /dev/null 2>&1 && \
        log "  ✅ Uploaded to Supabase Storage" || \
        warn "  ⚠️  Supabase upload failed (bucket may not exist)"
fi

# ── Cleanup Old Backups ──────────────────────────
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
DELETED=$(find "${BACKUP_DIR}" -name "backup_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete -print | wc -l)
DELETED_META=$(find "${BACKUP_DIR}" -name "backup_*.meta.json" -mtime "+${RETENTION_DAYS}" -delete -print | wc -l)
log "  Removed ${DELETED} old backups and ${DELETED_META} metadata files"

# ── Summary ──────────────────────────────────────
echo ""
log "══════════════════════════════════════════════"
log "  Backup Summary"
log "══════════════════════════════════════════════"
log "  File:       ${BACKUP_FILE}"
log "  Size:       ${BACKUP_SIZE_MB}MB"
log "  Retention:  ${RETENTION_DAYS} days"
log "  S3:         ${BACKUP_S3_BUCKET:-not configured}"
log "══════════════════════════════════════════════"
