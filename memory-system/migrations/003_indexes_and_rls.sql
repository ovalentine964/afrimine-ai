-- Migration 003: Indexes and Row Level Security
-- Performance indexes and RLS policies for multi-tenant access.

-- =============================================================================
-- PERFORMANCE INDEXES
-- =============================================================================

-- Agent sessions
CREATE INDEX IF NOT EXISTS idx_sessions_active
    ON agent_sessions (user_id, status)
    WHERE status IN ('active', 'paused');

CREATE INDEX IF NOT EXISTS idx_sessions_pipeline
    ON agent_sessions (pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_sessions_expires
    ON agent_sessions (expires_at)
    WHERE status = 'active';

-- Analysis history
CREATE INDEX IF NOT EXISTS idx_analysis_user
    ON analysis_history (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_mineral
    ON analysis_history (mineral_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_confidence
    ON analysis_history (confidence_score DESC)
    WHERE confidence_score IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_analysis_validation
    ON analysis_history (validation_status, created_at DESC);

-- Geological knowledge
CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON geological_knowledge (category);

CREATE INDEX IF NOT EXISTS idx_knowledge_minerals
    ON geological_knowledge USING GIN (related_minerals);

CREATE INDEX IF NOT EXISTS idx_knowledge_regions
    ON geological_knowledge USING GIN (related_regions);

CREATE INDEX IF NOT EXISTS idx_knowledge_verified
    ON geological_knowledge (verified, category)
    WHERE verified = true;

-- Mineral patterns
CREATE INDEX IF NOT EXISTS idx_patterns_type
    ON mineral_patterns (pattern_type, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_patterns_regions
    ON mineral_patterns USING GIN (applicable_regions);

CREATE INDEX IF NOT EXISTS idx_patterns_status
    ON mineral_patterns (status, confidence DESC);

-- Learned workflows
CREATE INDEX IF NOT EXISTS idx_workflows_type
    ON learned_workflows (workflow_type, success_rate DESC);

CREATE INDEX IF NOT EXISTS idx_workflows_minerals
    ON learned_workflows USING GIN (applicable_minerals);

CREATE INDEX IF NOT EXISTS idx_workflows_regions
    ON learned_workflows USING GIN (applicable_regions);

-- Long-term memory
CREATE INDEX IF NOT EXISTS idx_ltm_namespace
    ON agent_long_term_memory (namespace, key);

CREATE INDEX IF NOT EXISTS idx_ltm_category
    ON agent_long_term_memory (category)
    WHERE category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ltm_expires
    ON agent_long_term_memory (expires_at)
    WHERE expires_at IS NOT NULL;

-- Checkpoints
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
    ON checkpoints (thread_id, created_at DESC);

-- Sync log
CREATE INDEX IF NOT EXISTS idx_sync_device
    ON sync_log (device_id, synced_at DESC);

CREATE INDEX IF NOT EXISTS idx_sync_entity
    ON sync_log (entity_type, entity_id);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Agent sessions: users see only their own
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own sessions" ON agent_sessions
    FOR ALL USING (auth.uid()::text = user_id);

CREATE POLICY "Service role sees all sessions" ON agent_sessions
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Analysis history: users see only their own
ALTER TABLE analysis_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own analyses" ON analysis_history
    FOR ALL USING (auth.uid()::text = user_id);

CREATE POLICY "Service role sees all analyses" ON analysis_history
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Geological knowledge: public read, admin write
ALTER TABLE geological_knowledge ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Knowledge public read" ON geological_knowledge
    FOR SELECT USING (true);

CREATE POLICY "Knowledge service role write" ON geological_knowledge
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Mineral patterns: public read, admin write
ALTER TABLE mineral_patterns ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Patterns public read" ON mineral_patterns
    FOR SELECT USING (true);

CREATE POLICY "Patterns service role write" ON mineral_patterns
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Learned workflows: public read, admin write
ALTER TABLE learned_workflows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Workflows public read" ON learned_workflows
    FOR SELECT USING (true);

CREATE POLICY "Workflows service role write" ON learned_workflows
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Long-term memory: users see own namespace, system is public
ALTER TABLE agent_long_term_memory ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own LTM" ON agent_long_term_memory
    FOR ALL USING (
        namespace LIKE 'user:' || auth.uid()::text || '%'
        OR namespace NOT LIKE 'user:%'
    );

CREATE POLICY "Service role sees all LTM" ON agent_long_term_memory
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Checkpoints: service role only (LangGraph manages these)
ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Checkpoints service role" ON checkpoints
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

ALTER TABLE checkpoint_writes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Checkpoint writes service role" ON checkpoint_writes
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Sync log: users see own device syncs
ALTER TABLE sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own syncs" ON sync_log
    FOR ALL USING (auth.uid()::text = device_id);

CREATE POLICY "Service role sees all syncs" ON sync_log
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

-- Expire old sessions (called by consolidation job)
CREATE OR REPLACE FUNCTION expire_old_sessions()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE agent_sessions
    SET status = 'expired'
    WHERE status = 'active'
      AND expires_at < NOW();

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$;

-- Get memory usage stats
CREATE OR REPLACE FUNCTION get_memory_stats()
RETURNS TABLE (
    table_name TEXT,
    row_count BIGINT,
    size_mb NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.relname::TEXT,
        c.reltup::BIGINT,
        ROUND(pg_total_relation_size(c.oid) / 1024.0 / 1024.0, 2) AS size_mb
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
    ORDER BY pg_total_relation_size(c.oid) DESC;
END;
$$;
