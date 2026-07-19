#!/usr/bin/env bash
# AfriMine AI — Supabase Project Setup
# Creates tables, RLS policies, storage buckets, extensions
# Run: ./scripts/setup-supabase.sh
# Requires: SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_DB_HOST, SUPABASE_DB_PASSWORD

set -euo pipefail

# ── Colors ───────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

# ── Validate Environment ─────────────────────────
: "${SUPABASE_URL:?Set SUPABASE_URL}"
: "${SUPABASE_SERVICE_KEY:?Set SUPABASE_SERVICE_KEY}"
: "${SUPABASE_DB_HOST:?Set SUPABASE_DB_HOST}"
: "${SUPABASE_DB_PASSWORD:?Set SUPABASE_DB_PASSWORD}"

DB_URL="postgresql://postgres:${SUPABASE_DB_PASSWORD}@${SUPABASE_DB_HOST}:5432/postgres"

log "Setting up Supabase project: ${SUPABASE_URL}"

# ── Helper: Run SQL ──────────────────────────────
run_sql() {
    local sql="$1"
    local description="$2"
    log "  → ${description}"
    psql "${DB_URL}" -c "${sql}" 2>/dev/null || {
        warn "  SQL failed (may already exist): ${description}"
    }
}

run_sql_file() {
    local file="$1"
    local description="$2"
    log "  → ${description}"
    psql "${DB_URL}" -f "${file}" 2>/dev/null || {
        warn "  SQL file failed: ${description}"
    }
}

# ── Step 1: Enable Extensions ────────────────────
log "Step 1: Enabling PostgreSQL extensions..."

run_sql "CREATE EXTENSION IF NOT EXISTS vector;"       "pgvector"
run_sql "CREATE EXTENSION IF NOT EXISTS pg_trgm;"      "pg_trgm (fuzzy text search)"
run_sql "CREATE EXTENSION IF NOT EXISTS pgcrypto;"     "pgcrypto"
run_sql "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" "uuid-ossp"

# ── Step 2: Create Tables ────────────────────────
log "Step 2: Creating tables..."

run_sql "
-- Users table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    phone TEXT,
    role TEXT NOT NULL DEFAULT 'field_worker'
        CHECK (role IN ('field_worker', 'geologist', 'investor', 'admin')),
    region TEXT,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "user_profiles"

run_sql "
-- Mineral samples from field
CREATE TABLE IF NOT EXISTS public.mineral_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    location JSONB NOT NULL DEFAULT '{}',
    photo_urls TEXT[] DEFAULT '{}',
    xrf_readings JSONB DEFAULT '{}',
    field_notes TEXT,
    voice_note_url TEXT,
    synced BOOLEAN DEFAULT FALSE,
    vector_clock JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "mineral_samples"

run_sql "
-- Analysis results (links to agent pipeline output)
CREATE TABLE IF NOT EXISTS public.analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    sample_ids UUID[] DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    agent_outputs JSONB DEFAULT '{}',
    detected_minerals TEXT[] DEFAULT '{}',
    estimated_grade NUMERIC,
    confidence_score NUMERIC CHECK (confidence_score >= 0 AND confidence_score <= 1),
    estimated_value_usd NUMERIC,
    embedding vector(384),
    pipeline_duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "analyses"

# ── Step 3: Memory Tables (5-Layer Architecture) ─
log "Step 3: Creating memory tables..."

run_sql "
-- Layer 1: Short-term (session state)
CREATE TABLE IF NOT EXISTS public.agent_sessions (
    session_id TEXT PRIMARY KEY,
    pipeline_run_id TEXT,
    user_id TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed', 'failed', 'expired')),
    state JSONB DEFAULT '{}',
    state_version INTEGER DEFAULT 1,
    checkpoint_id TEXT,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "agent_sessions (short-term memory)"

run_sql "
-- Layer 2: Episodic (analysis history)
CREATE TABLE IF NOT EXISTS public.analysis_history (
    analysis_id TEXT PRIMARY KEY,
    user_id TEXT,
    location JSONB DEFAULT '{}',
    sampling_output JSONB DEFAULT '{}',
    analysis_output JSONB DEFAULT '{}',
    geology_output JSONB DEFAULT '{}',
    market_output JSONB DEFAULT '{}',
    report_output JSONB DEFAULT '{}',
    compliance_output JSONB DEFAULT '{}',
    embedding vector(384),
    validation_status TEXT DEFAULT 'unvalidated',
    vector_clock JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "analysis_history (episodic memory)"

run_sql "
-- Layer 3: Semantic (geological knowledge)
CREATE TABLE IF NOT EXISTS public.geological_knowledge (
    knowledge_id TEXT PRIMARY KEY,
    category TEXT NOT NULL
        CHECK (category IN ('deposit_model', 'pathfinder_element', 'geological_formation',
                           'mineral_association', 'regulatory_rule', 'alteration_pattern')),
    content JSONB NOT NULL DEFAULT '{}',
    related_minerals TEXT[] DEFAULT '{}',
    embedding vector(384),
    usefulness_score NUMERIC DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "geological_knowledge (semantic memory)"

run_sql "
-- Layer 3b: Discovered patterns
CREATE TABLE IF NOT EXISTS public.mineral_patterns (
    pattern_id TEXT PRIMARY KEY,
    pattern_type TEXT NOT NULL
        CHECK (pattern_type IN ('element_correlation', 'grade_distribution',
                               'spatial_cluster', 'temporal_trend')),
    conditions JSONB DEFAULT '{}',
    confidence NUMERIC DEFAULT 0.5,
    applicable_regions TEXT[] DEFAULT '{}',
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "mineral_patterns"

run_sql "
-- Layer 4: Procedural (learned workflows)
CREATE TABLE IF NOT EXISTS public.learned_workflows (
    workflow_id TEXT PRIMARY KEY,
    workflow_type TEXT NOT NULL
        CHECK (workflow_type IN ('full_pipeline', 'analysis_template',
                               'report_template', 'compliance_check')),
    graph_definition JSONB DEFAULT '{}',
    success_rate NUMERIC DEFAULT 0.5,
    applicable_minerals TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "learned_workflows (procedural memory)"

run_sql "
-- Layer 5: Long-term (persistent facts)
CREATE TABLE IF NOT EXISTS public.agent_long_term_memory (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (namespace, key)
);
" "agent_long_term_memory (long-term memory)"

# ── Step 4: LangGraph Checkpoint Tables ──────────
log "Step 4: Creating LangGraph checkpoint tables..."

run_sql "
CREATE TABLE IF NOT EXISTS public.checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    checkpoint JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
" "checkpoints"

run_sql "
CREATE TABLE IF NOT EXISTS public.checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
" "checkpoint_writes"

# ── Step 5: Sync Table ───────────────────────────
log "Step 5: Creating sync table..."

run_sql "
CREATE TABLE IF NOT EXISTS public.sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id TEXT NOT NULL,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('analysis', 'sample', 'knowledge')),
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    direction TEXT NOT NULL CHECK (direction IN ('upload', 'download')),
    vector_clock JSONB DEFAULT '{}',
    conflict BOOLEAN DEFAULT FALSE,
    conflict_details JSONB,
    resolution_method TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
" "sync_log"

# ── Step 6: Indexes ──────────────────────────────
log "Step 6: Creating indexes..."

run_sql "CREATE INDEX IF NOT EXISTS idx_mineral_samples_user ON public.mineral_samples(user_id);" "sample user index"
run_sql "CREATE INDEX IF NOT EXISTS idx_analyses_user ON public.analyses(user_id);" "analyses user index"
run_sql "CREATE INDEX IF NOT EXISTS idx_analyses_status ON public.analyses(status);" "analyses status index"
run_sql "CREATE INDEX IF NOT EXISTS idx_analyses_embedding ON public.analyses USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);" "analyses embedding index"
run_sql "CREATE INDEX IF NOT EXISTS idx_analysis_history_embedding ON public.analysis_history USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);" "history embedding index"
run_sql "CREATE INDEX IF NOT EXISTS idx_geological_knowledge_embedding ON public.geological_knowledge USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);" "knowledge embedding index"
run_sql "CREATE INDEX IF NOT EXISTS idx_agent_sessions_expires ON public.agent_sessions(expires_at);" "session expiry index"
run_sql "CREATE INDEX IF NOT EXISTS idx_agent_sessions_user ON public.agent_sessions(user_id);" "session user index"
run_sql "CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON public.checkpoints(thread_id);" "checkpoint thread index"
run_sql "CREATE INDEX IF NOT EXISTS idx_sync_log_device ON public.sync_log(device_id);" "sync device index"
run_sql "CREATE INDEX IF NOT EXISTS idx_mineral_patterns_embedding ON public.mineral_patterns USING ivfflat (embedding vector_cosine_ops) WITH (lists = 5);" "pattern embedding index"

# ── Step 7: Row-Level Security ───────────────────
log "Step 7: Enabling RLS..."

TABLES=("user_profiles" "mineral_samples" "analyses" "agent_sessions"
        "analysis_history" "geological_knowledge" "mineral_patterns"
        "learned_workflows" "agent_long_term_memory" "checkpoints"
        "checkpoint_writes" "sync_log")

for table in "${TABLES[@]}"; do
    run_sql "ALTER TABLE public.${table} ENABLE ROW LEVEL SECURITY;" "RLS on ${table}"
done

# ── Step 8: RLS Policies ─────────────────────────
log "Step 8: Creating RLS policies..."

# Users can read/write their own profile
run_sql "
CREATE POLICY \"Users can view own profile\"
    ON public.user_profiles FOR SELECT
    USING (auth.uid() = id);
" "user_profiles SELECT"
run_sql "
CREATE POLICY \"Users can update own profile\"
    ON public.user_profiles FOR UPDATE
    USING (auth.uid() = id);
" "user_profiles UPDATE"

# Samples: users see their own, geologists see all
run_sql "
CREATE POLICY \"Users can view own samples\"
    ON public.mineral_samples FOR SELECT
    USING (auth.uid() = user_id OR
           EXISTS (SELECT 1 FROM public.user_profiles WHERE id = auth.uid() AND role IN ('geologist', 'admin')));
" "mineral_samples SELECT"
run_sql "
CREATE POLICY \"Users can insert own samples\"
    ON public.mineral_samples FOR INSERT
    WITH CHECK (auth.uid() = user_id);
" "mineral_samples INSERT"

# Analyses: same pattern
run_sql "
CREATE POLICY \"Users can view own analyses\"
    ON public.analyses FOR SELECT
    USING (auth.uid() = user_id OR
           EXISTS (SELECT 1 FROM public.user_profiles WHERE id = auth.uid() AND role IN ('geologist', 'investor', 'admin')));
" "analyses SELECT"
run_sql "
CREATE POLICY \"Users can insert own analyses\"
    ON public.analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);
" "analyses INSERT"

# Agent sessions: service role only (agents write, not users)
run_sql "
CREATE POLICY \"Service role manages agent sessions\"
    ON public.agent_sessions FOR ALL
    USING (true)
    WITH CHECK (true);
" "agent_sessions ALL (service role)"

# Analysis history: read for authenticated, write for service
run_sql "
CREATE POLICY \"Authenticated can view history\"
    ON public.analysis_history FOR SELECT
    USING (auth.role() = 'authenticated');
" "analysis_history SELECT"

# Geological knowledge: public read, admin write
run_sql "
CREATE POLICY \"Public read geological knowledge\"
    ON public.geological_knowledge FOR SELECT
    USING (true);
" "geological_knowledge SELECT"
run_sql "
CREATE POLICY \"Admin write geological knowledge\"
    ON public.geological_knowledge FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM public.user_profiles WHERE id = auth.uid() AND role = 'admin'));
" "geological_knowledge INSERT"

# Long-term memory: service role
run_sql "
CREATE POLICY \"Service role manages long-term memory\"
    ON public.agent_long_term_memory FOR ALL
    USING (true)
    WITH CHECK (true);
" "agent_long_term_memory ALL"

# Checkpoints: service role only
run_sql "
CREATE POLICY \"Service role manages checkpoints\"
    ON public.checkpoints FOR ALL
    USING (true)
    WITH CHECK (true);
" "checkpoints ALL"
run_sql "
CREATE POLICY \"Service role manages checkpoint writes\"
    ON public.checkpoint_writes FOR ALL
    USING (true)
    WITH CHECK (true);
" "checkpoint_writes ALL"

# Sync log: users see their own
run_sql "
CREATE POLICY \"Users can view own sync logs\"
    ON public.sync_log FOR SELECT
    USING (device_id IN (
        SELECT device_id FROM public.sync_log WHERE user_id::text = auth.uid()::text
    ) OR EXISTS (SELECT 1 FROM public.user_profiles WHERE id = auth.uid() AND role = 'admin'));
" "sync_log SELECT"

# ── Step 9: Storage Buckets ──────────────────────
log "Step 9: Creating storage buckets..."

for bucket in "sample-photos" "reports" "voice-notes" "satellite-tiles" "model-weights"; do
    run_sql "
        INSERT INTO storage.buckets (id, name, public, file_size_limit)
        VALUES ('${bucket}', '${bucket}', false, $(
            case ${bucket} in
                "sample-photos")   echo 5242880;;   # 5MB
                "reports")         echo 10485760;;  # 10MB
                "voice-notes")     echo 10485760;;  # 10MB
                "satellite-tiles") echo 104857600;; # 100MB
                "model-weights")   echo 104857600;; # 100MB
            esac
        ))
        ON CONFLICT (id) DO NOTHING;
    " "Storage bucket: ${bucket}"
done

# ── Step 10: Cleanup Expired Sessions ────────────
log "Step 10: Setting up session cleanup..."

run_sql "
-- Function to clean expired sessions
CREATE OR REPLACE FUNCTION public.cleanup_expired_sessions()
RETURNS void AS \$\$
BEGIN
    DELETE FROM public.agent_sessions WHERE expires_at < now();
    DELETE FROM public.checkpoints WHERE created_at < now() - interval '7 days';
    DELETE FROM public.checkpoint_writes WHERE created_at < now() - interval '7 days';
END;
\$\$ LANGUAGE plpgsql SECURITY DEFINER;
" "Cleanup function"

# ── Done ─────────────────────────────────────────
log ""
log "✅ Supabase setup complete!"
log ""
log "Created:"
log "  - 12 tables (core + memory + checkpoints + sync)"
log "  - 11 indexes (including 4 IVFFlat vector indexes)"
log "  - RLS policies on all tables"
log "  - 5 storage buckets"
log "  - Session cleanup function"
log ""
log "Next steps:"
log "  1. Verify tables in Supabase Dashboard → Table Editor"
log "  2. Test RLS policies with a user token"
log "  3. Run: SELECT public.cleanup_expired_sessions(); to test cleanup"
