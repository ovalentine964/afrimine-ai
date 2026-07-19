-- =============================================================================
-- AfriMine AI — Layered Memory Schema
-- Supabase (PostgreSQL + pgvector)
-- Free Tier: 500MB database, 1GB storage
-- =============================================================================
-- Run: CREATE EXTENSION IF NOT EXISTS vector;  (in Supabase SQL Editor first)

-- =============================================================================
-- LAYER 1: SHORT-TERM MEMORY — Session State
-- =============================================================================
-- LangGraph checkpoint storage + active agent sessions.
-- Auto-cleanup: sessions older than 24h are purged by consolidation job.

CREATE TABLE IF NOT EXISTS agent_sessions (
    -- Identity
    session_id        TEXT PRIMARY KEY,               -- UUID, LangGraph thread_id
    pipeline_run_id   TEXT NOT NULL,                  -- Groups sessions in a pipeline run
    user_id           TEXT NOT NULL,                  -- Supabase auth user

    -- State
    status            TEXT NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'paused', 'completed', 'failed', 'expired')),
    current_agent     TEXT,                           -- Which agent is currently running
    agents_completed  TEXT[] DEFAULT '{}',            -- Array of completed agent names

    -- LangGraph state (full pipeline state as JSONB)
    state             JSONB NOT NULL DEFAULT '{}',    -- AfriMineState snapshot
    state_version     INTEGER NOT NULL DEFAULT 1,     -- Optimistic concurrency

    -- Checkpoint data for LangGraph
    checkpoint_id     TEXT,                           -- LangGraph checkpoint ID
    checkpoint_data   JSONB,                          -- Serialized checkpoint
    parent_checkpoint TEXT,                           -- Previous checkpoint (linked list)

    -- Metadata
    location          JSONB,                          -- {lat, lon, region, country}
    mineral_type      TEXT,                           -- Primary mineral being analyzed
    priority          TEXT DEFAULT 'normal'
                      CHECK (priority IN ('low', 'normal', 'high', 'urgent')),

    -- Timestamps
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    completed_at      TIMESTAMPTZ
);

-- Index for active session lookup
CREATE INDEX IF NOT EXISTS idx_sessions_active
    ON agent_sessions (user_id, status)
    WHERE status IN ('active', 'paused');

CREATE INDEX IF NOT EXISTS idx_sessions_pipeline
    ON agent_sessions (pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_sessions_expires
    ON agent_sessions (expires_at)
    WHERE status = 'active';

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_session_updated
    BEFORE UPDATE ON agent_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_session_timestamp();


-- =============================================================================
-- LAYER 2: EPISODIC MEMORY — Analysis History
-- =============================================================================
-- Complete record of every mineral analysis. Enables "find similar" queries.

CREATE TABLE IF NOT EXISTS analysis_history (
    -- Identity
    analysis_id       TEXT PRIMARY KEY,               -- UUID
    session_id        TEXT REFERENCES agent_sessions(session_id) ON DELETE SET NULL,
    user_id           TEXT NOT NULL,

    -- Input
    location          JSONB NOT NULL,                 -- {lat, lon, region, country, elevation}
    sample_data       JSONB NOT NULL,                 -- Photo URLs, XRF data, field notes
    mineral_type      TEXT,                           -- User-reported or AI-detected
    sample_count      INTEGER DEFAULT 1,              -- Number of samples in this analysis

    -- Agent Outputs (one column per agent)
    sampling_output   JSONB,                          -- Sampling Agent results
    analysis_output   JSONB,                          -- Analysis Agent results
    geology_output    JSONB,                          -- Geology Agent results
    market_output     JSONB,                          -- Market Agent results
    report_output     JSONB,                          -- Report Agent results
    compliance_output JSONB,                          -- Compliance Agent results

    -- Summary (extracted from agent outputs)
    detected_minerals TEXT[],                         -- List of detected minerals
    estimated_grade   NUMERIC,                        -- Estimated mineral grade
    grade_unit        TEXT,                           -- ppm, %, g/t, etc.
    confidence_score  NUMERIC                         -- 0.0 - 1.0
                      CHECK (confidence_score >= 0 AND confidence_score <= 1),
    estimated_value   NUMERIC,                        -- USD value estimate
    value_currency    TEXT DEFAULT 'USD',

    -- Quality
    data_quality      TEXT DEFAULT 'preliminary'
                      CHECK (data_quality IN ('preliminary', 'indicated', 'inferred', 'measured')),
    validation_status TEXT DEFAULT 'pending'
                      CHECK (validation_status IN ('pending', 'validated', 'rejected', 'needs_review')),

    -- Vector embedding for similarity search (384-dim, all-MiniLM-L6-v2)
    embedding         vector(384),

    -- Metadata
    pipeline_duration_ms  INTEGER,                    -- Total pipeline execution time
    agents_used       TEXT[] DEFAULT '{}',            -- Which agents participated
    model_used        TEXT DEFAULT 'gemini-2.5-flash',
    is_anomalous      BOOLEAN DEFAULT FALSE,          -- Flagged by pattern detection

    -- Timestamps
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Similarity search index (IVFFlat for <100K rows, switch to HNSW later)
CREATE INDEX IF NOT EXISTS idx_analysis_embedding
    ON analysis_history USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_analysis_user
    ON analysis_history (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_mineral
    ON analysis_history (mineral_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_location
    ON analysis_history ((location->>'region'), created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_confidence
    ON analysis_history (confidence_score DESC)
    WHERE confidence_score IS NOT NULL;


-- =============================================================================
-- LAYER 3: SEMANTIC MEMORY — Geological Knowledge Base
-- =============================================================================
-- Structured geological knowledge: deposit models, pathfinder elements,
-- alteration signatures, tectonic settings, etc.

CREATE TABLE IF NOT EXISTS geological_knowledge (
    -- Identity
    knowledge_id      TEXT PRIMARY KEY,               -- UUID
    category          TEXT NOT NULL
                      CHECK (category IN (
                          'deposit_model',            -- e.g., "orogenic gold", "VMS", "porphyry"
                          'pathfinder_element',       -- e.g., As→Au correlation
                          'alteration_signature',     -- e.g., sericitization, silicification
                          'tectonic_setting',         -- e.g., greenstone belt, shear zone
                          'mineral_association',      -- e.g., pyrite+arsenopyrite+gold
                          'grade_threshold',          -- e.g., economic cut-off grades
                          'exploration_indicator',    -- e.g., soil anomaly patterns
                          'regulatory_rule',          -- e.g., Kenya Mining Act requirements
                          'processing_method',        -- e.g., gravity separation for gold
                          'geological_region'         -- e.g., Migori Belt specifics
                      )),

    -- Content
    title             TEXT NOT NULL,                  -- Human-readable title
    description       TEXT NOT NULL,                  -- Full description
    content           JSONB NOT NULL,                 -- Structured data (varies by category)

    -- Relationships
    related_minerals  TEXT[],                         -- Minerals this knowledge relates to
    related_regions   TEXT[],                         -- Geographic regions
    related_deposit_models TEXT[],                    -- Related deposit model names
    parent_knowledge  TEXT REFERENCES geological_knowledge(knowledge_id),

    -- Confidence & Source
    confidence        NUMERIC DEFAULT 0.8             -- How reliable is this knowledge
                      CHECK (confidence >= 0 AND confidence <= 1),
    source            TEXT,                           -- "USGS", "academic paper", "field observation"
    source_url        TEXT,
    verified          BOOLEAN DEFAULT FALSE,

    -- Vector embedding for semantic search
    embedding         vector(384),

    -- Usage tracking
    times_referenced  INTEGER DEFAULT 0,
    last_referenced   TIMESTAMPTZ,
    usefulness_score  NUMERIC DEFAULT 0.5,            -- Feedback-adjusted score

    -- Timestamps
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector search index
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON geological_knowledge USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Category + mineral lookup
CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON geological_knowledge (category);

CREATE INDEX IF NOT EXISTS idx_knowledge_minerals
    ON geological_knowledge USING GIN (related_minerals);

CREATE INDEX IF NOT EXISTS idx_knowledge_regions
    ON geological_knowledge USING GIN (related_regions);


-- =============================================================================
-- LAYER 3b: MINERAL PATTERNS — Discovered Patterns
-- =============================================================================
-- Patterns discovered across multiple analyses (e.g., "As > 50ppm correlates
-- with gold in Migori Belt with 85% confidence across 23 analyses").

CREATE TABLE IF NOT EXISTS mineral_patterns (
    -- Identity
    pattern_id        TEXT PRIMARY KEY,               -- UUID
    pattern_type      TEXT NOT NULL
                      CHECK (pattern_type IN (
                          'element_correlation',      -- e.g., As→Au
                          'grade_distribution',       -- e.g., log-normal gold grades
                          'spatial_cluster',          -- e.g., high-grade zone at (lat, lon)
                          'alteration_pattern',       -- e.g., sericite+quartz = gold
                          'depth_indicator',          -- e.g., surface geochem → depth potential
                          'economic_threshold',       -- e.g., cut-off grade for viability
                          'failure_pattern'           -- e.g., "low As + high Fe = barren"
                      )),

    -- Pattern Definition
    name              TEXT NOT NULL,                  -- Human-readable name
    description       TEXT NOT NULL,                  -- What this pattern means
    conditions        JSONB NOT NULL,                 -- Pattern conditions (searchable)
    -- Example: {"element": "As", "threshold_ppm": 50, "correlates_with": "Au", "direction": "positive"}

    -- Statistics
    support_count     INTEGER NOT NULL DEFAULT 0,     -- Number of analyses supporting this
    confidence        NUMERIC NOT NULL DEFAULT 0.5    -- Statistical confidence
                      CHECK (confidence >= 0 AND confidence <= 1),
    lift              NUMERIC,                        -- Lift metric (if applicable)

    -- Geographic Scope
    applicable_regions TEXT[],                        -- Regions where this pattern holds
    applicable_deposit_models TEXT[],                 -- Deposit models this applies to

    -- Supporting Evidence
    supporting_analyses TEXT[],                       -- analysis_ids that support this pattern
    contradicting_analyses TEXT[],                    -- analysis_ids that contradict it

    -- Status
    status            TEXT DEFAULT 'proposed'
                      CHECK (status IN ('proposed', 'validated', 'deprecated', 'under_review')),
    validated_by      TEXT,                           -- User/expert who validated

    -- Embedding
    embedding         vector(384),

    -- Timestamps
    first_observed    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_patterns_type
    ON mineral_patterns (pattern_type, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_patterns_regions
    ON mineral_patterns USING GIN (applicable_regions);

CREATE INDEX IF NOT EXISTS idx_patterns_embedding
    ON mineral_patterns USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 5);


-- =============================================================================
-- LAYER 4: PROCEDURAL MEMORY — Learned Workflows
-- =============================================================================
-- Successful analysis workflows that can be replayed or used as templates.

CREATE TABLE IF NOT EXISTS learned_workflows (
    -- Identity
    workflow_id       TEXT PRIMARY KEY,               -- UUID
    name              TEXT NOT NULL,                  -- Human-readable name
    description       TEXT NOT NULL,                  -- What this workflow does

    -- Workflow Definition
    workflow_type     TEXT NOT NULL
                      CHECK (workflow_type IN (
                          'full_pipeline',            -- Complete 6-agent pipeline
                          'analysis_template',        -- Pre-configured analysis parameters
                          'error_recovery',           -- How to recover from specific errors
                          'optimization',             -- Workflow that improved performance
                          'validation_check',         -- Checks that catch bad results
                          'agent_sequence'            -- Optimal agent execution order
                      )),

    -- The workflow as a LangGraph-compatible JSON
    graph_definition  JSONB NOT NULL,                 -- Nodes, edges, conditions
    -- Example: {"nodes": [...], "edges": [...], "conditions": {...}}

    -- Configuration
    applicable_minerals TEXT[],                       -- Which minerals this applies to
    applicable_regions  TEXT[],                       -- Which regions this applies to
    required_agents     TEXT[] NOT NULL,              -- Which agents are needed
    optional_agents     TEXT[] DEFAULT '{}',          -- Which agents are optional

    -- Performance
    avg_duration_ms   INTEGER,                        -- Average execution time
    success_rate      NUMERIC                         -- 0.0 - 1.0
                      CHECK (success_rate >= 0 AND success_rate <= 1),
    avg_confidence    NUMERIC,                        -- Average output confidence

    -- Usage
    times_used        INTEGER DEFAULT 0,
    last_used         TIMESTAMPTZ,
    source_analysis   TEXT REFERENCES analysis_history(analysis_id),  -- Original analysis

    -- Status
    status            TEXT DEFAULT 'active'
                      CHECK (status IN ('active', 'deprecated', 'experimental')),

    -- Timestamps
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflows_type
    ON learned_workflows (workflow_type, success_rate DESC);

CREATE INDEX IF NOT EXISTS idx_workflows_minerals
    ON learned_workflows USING GIN (applicable_minerals);

CREATE INDEX IF NOT EXISTS idx_workflows_regions
    ON learned_workflows USING GIN (applicable_regions);


-- =============================================================================
-- LAYER 5: LONG-TERM MEMORY — Persistent Facts
-- =============================================================================
-- Facts that persist across all sessions: user preferences, calibration data,
-- model performance, region-specific learnings.

CREATE TABLE IF NOT EXISTS agent_long_term_memory (
    -- Identity
    memory_id         TEXT PRIMARY KEY,               -- UUID
    namespace         TEXT NOT NULL,                  -- Logical grouping
    -- Namespaces: "user:{id}", "region:{name}", "model:{name}", "system"

    -- Content
    key               TEXT NOT NULL,                  -- Fact key (unique within namespace)
    value             JSONB NOT NULL,                 -- Fact value (any JSON)
    -- Example: namespace="region:migori_belt", key="avg_gold_grade", value={"ppm": 2.3, "n": 45}

    -- Metadata
    category          TEXT,                           -- Optional categorization
    confidence        NUMERIC DEFAULT 1.0,            -- How certain we are
    source            TEXT,                           -- Where this fact came from

    -- Lifecycle
    expires_at        TIMESTAMPTZ,                    -- Optional TTL
    superseded_by     TEXT REFERENCES agent_long_term_memory(memory_id),

    -- Timestamps
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one value per namespace+key
    UNIQUE (namespace, key)
);

CREATE INDEX IF NOT EXISTS idx_ltm_namespace
    ON agent_long_term_memory (namespace, key);

CREATE INDEX IF NOT EXISTS idx_ltm_category
    ON agent_long_term_memory (category)
    WHERE category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ltm_expires
    ON agent_long_term_memory (expires_at)
    WHERE expires_at IS NOT NULL;


-- =============================================================================
-- LANGGRAPH CHECKPOINT TABLES
-- =============================================================================
-- Standard LangGraph checkpoint storage, compatible with
-- langgraph-checkpoint-postgres.

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id         TEXT NOT NULL,
    checkpoint_ns     TEXT NOT NULL DEFAULT '',
    checkpoint_id     TEXT NOT NULL,
    parent_checkpoint TEXT,
    checkpoint        JSONB NOT NULL,
    metadata          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
    ON checkpoints (thread_id, created_at DESC);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id         TEXT NOT NULL,
    checkpoint_ns     TEXT NOT NULL DEFAULT '',
    checkpoint_id     TEXT NOT NULL,
    task_id           TEXT NOT NULL,
    idx               INTEGER NOT NULL,
    channel           TEXT NOT NULL,
    value             JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);


-- =============================================================================
-- SYNC TRACKING (Offline-First)
-- =============================================================================
-- Tracks what has been synced between Flutter (local SQLite) and Supabase.

CREATE TABLE IF NOT EXISTS sync_log (
    sync_id           TEXT PRIMARY KEY,               -- UUID
    device_id         TEXT NOT NULL,                   -- Flutter device identifier
    entity_type       TEXT NOT NULL,                   -- 'analysis', 'sample', 'knowledge'
    entity_id         TEXT NOT NULL,                   -- ID of the synced entity
    action            TEXT NOT NULL
                      CHECK (action IN ('create', 'update', 'delete')),
    direction         TEXT NOT NULL
                      CHECK (direction IN ('upload', 'download')),
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    conflict          BOOLEAN DEFAULT FALSE,           -- Was there a sync conflict?
    resolution        TEXT                             -- How conflict was resolved
                      CHECK (resolution IS NULL OR resolution IN ('server_wins', 'client_wins', 'merged'))
);

CREATE INDEX IF NOT EXISTS idx_sync_device
    ON sync_log (device_id, synced_at DESC);

CREATE INDEX IF NOT EXISTS idx_sync_entity
    ON sync_log (entity_type, entity_id);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================
-- Users can only access their own data. Agents access via service role.

ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_long_term_memory ENABLE ROW LEVEL SECURITY;

-- Users see only their own sessions
CREATE POLICY "Users see own sessions" ON agent_sessions
    FOR ALL USING (auth.uid()::text = user_id);

-- Users see only their own analyses
CREATE POLICY "Users see own analyses" ON analysis_history
    FOR ALL USING (auth.uid()::text = user_id);

-- Knowledge base is public-read, admin-write
ALTER TABLE geological_knowledge ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Knowledge is public read" ON geological_knowledge
    FOR SELECT USING (true);
CREATE POLICY "Knowledge is admin write" ON geological_knowledge
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Patterns are public-read
ALTER TABLE mineral_patterns ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Patterns are public read" ON mineral_patterns
    FOR SELECT USING (true);
CREATE POLICY "Patterns are service write" ON mineral_patterns
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- Workflows are public-read
ALTER TABLE learned_workflows ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Workflows are public read" ON learned_workflows
    FOR SELECT USING (true);
CREATE POLICY "Workflows are service write" ON learned_workflows
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- LTM: users see own, system facts are public
CREATE POLICY "Users see own LTM" ON agent_long_term_memory
    FOR ALL USING (
        namespace LIKE 'user:' || auth.uid()::text || '%'
        OR namespace NOT LIKE 'user:%'
    );

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


-- =============================================================================
-- AUDIT LOG TABLE (Kenya Mining Act Compliance)
-- =============================================================================
-- Append-only audit trail for all sensitive operations.
-- Required by Kenya Mining Act 2016 for license tracking, royalty calculations,
-- EIA compliance, and data retention.
-- Retention: 7 years (Kenya Mining Act requirement).

CREATE TABLE IF NOT EXISTS audit_log (
    -- Identity
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Who
    user_id         TEXT,                              -- Supabase auth user ID
    agent_name      TEXT,                              -- Agent role if action was by agent
    session_id      TEXT,                              -- LangGraph thread/session ID
    ip_address      INET,                              -- Client IP address
    user_agent      TEXT,                              -- Client user agent string

    -- What
    action          TEXT NOT NULL,                     -- 'READ', 'CREATE', 'UPDATE', 'DELETE', 'EXPORT',
                                                       -- 'LOGIN', 'AGENT_START', 'AGENT_COMPLETE',
                                                       -- 'TOOL_CALL', 'LLM_CALL', 'PROMPT_INJECTION_DETECTED'
    resource_type   TEXT NOT NULL,                     -- 'sample', 'analysis', 'report', 'landowner',
                                                       -- 'agent_execution', 'tool', 'llm', 'security'
    resource_id     TEXT,                              -- ID of the affected resource

    -- Details (structured)
    details         JSONB DEFAULT '{}',
    -- Examples:
    -- {"table": "mineral_samples", "columns": ["gps_lat", "gps_lon"], "row_count": 5}
    -- {"agent": "analysis", "tool": "classify_mineral", "input_hash": "abc123"}
    -- {"old_value": {"status": "pending"}, "new_value": {"status": "approved"}}
    -- {"model": "gemini-2.5-flash", "token_count": 1500, "latency_ms": 2300}

    -- Risk scoring
    risk_level      TEXT DEFAULT 'LOW'
                    CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- Kenya Mining Act compliance
    compliance_section TEXT,                           -- e.g., 'section_35', 'section_103', 'section_104'
    compliance_relevant BOOLEAN DEFAULT FALSE,         -- TRUE if this event is compliance-relevant

    -- Tamper detection
    checksum        TEXT                               -- SHA-256 of row contents
);

-- Indexes for common audit queries
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_log (agent_name);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_risk ON audit_log (risk_level) WHERE risk_level IN ('HIGH', 'CRITICAL');
CREATE INDEX IF NOT EXISTS idx_audit_compliance ON audit_log (compliance_relevant) WHERE compliance_relevant = TRUE;
CREATE INDEX IF NOT EXISTS idx_audit_section ON audit_log (compliance_section) WHERE compliance_section IS NOT NULL;

-- RLS: Append-only. Only admins can read. System can insert.
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Admins can read audit logs
CREATE POLICY "Admins read audit logs" ON audit_log
    FOR SELECT USING (
        auth.jwt()->>'role' = 'service_role'
        OR EXISTS (
            SELECT 1 FROM auth.users
            WHERE auth.uid() = id
            AND raw_user_meta_data->>'role' = 'admin'
        )
    );

-- System (service role) can insert
CREATE POLICY "System inserts audit logs" ON audit_log
    FOR INSERT WITH CHECK (TRUE);

-- Prevent updates and deletes (immutable audit trail)
CREATE POLICY "Audit log immutable update" ON audit_log
    FOR UPDATE USING (FALSE);
CREATE POLICY "Audit log immutable delete" ON audit_log
    FOR DELETE USING (FALSE);


-- =============================================================================
-- AUDIT LOG TRIGGER FUNCTIONS
-- =============================================================================
-- Automatic logging for sensitive table modifications.

CREATE OR REPLACE FUNCTION log_sensitive_modification()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        user_id,
        agent_name,
        action,
        resource_type,
        resource_id,
        details,
        risk_level,
        compliance_relevant
    ) VALUES (
        auth.uid()::text,
        current_setting('app.agent_name', TRUE),  -- Set by LangGraph agent
        TG_OP,                                     -- INSERT, UPDATE, DELETE
        TG_TABLE_NAME,
        COALESCE(
            (to_jsonb(NEW) ->> 'id'),
            (to_jsonb(OLD) ->> 'id'),
            (to_jsonb(NEW) ->> 'analysis_id'),
            (to_jsonb(OLD) ->> 'analysis_id'),
            (to_jsonb(NEW) ->> 'session_id'),
            (to_jsonb(OLD) ->> 'session_id'),
            'unknown'
        ),
        CASE
            WHEN TG_OP = 'DELETE' THEN
                jsonb_build_object('deleted_data', to_jsonb(OLD))
            WHEN TG_OP = 'UPDATE' THEN
                jsonb_build_object(
                    'old', to_jsonb(OLD),
                    'new', to_jsonb(NEW),
                    'changed_keys', (
                        SELECT jsonb_agg(key)
                        FROM jsonb_each(to_jsonb(NEW))
                        WHERE to_jsonb(OLD) -> key IS DISTINCT FROM to_jsonb(NEW) -> key
                    )
                )
            WHEN TG_OP = 'INSERT' THEN
                jsonb_build_object('new_data', to_jsonb(NEW))
        END,
        CASE
            WHEN TG_TABLE_NAME IN ('mineral_samples', 'analysis_history') THEN 'HIGH'
            WHEN TG_TABLE_NAME = 'audit_log' THEN 'CRITICAL'
            WHEN TG_TABLE_NAME = 'compliance_result' THEN 'HIGH'
            ELSE 'MEDIUM'
        END,
        CASE
            WHEN TG_TABLE_NAME IN ('analysis_history', 'mineral_samples') THEN TRUE
            ELSE FALSE
        END
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Apply audit triggers to sensitive tables
CREATE TRIGGER audit_mineral_samples
    AFTER INSERT OR UPDATE OR DELETE ON mineral_samples
    FOR EACH ROW EXECUTE FUNCTION log_sensitive_modification();

CREATE TRIGGER audit_analysis_history
    AFTER INSERT OR UPDATE OR DELETE ON analysis_history
    FOR EACH ROW EXECUTE FUNCTION log_sensitive_modification();

CREATE TRIGGER audit_geological_knowledge
    AFTER INSERT OR UPDATE OR DELETE ON geological_knowledge
    FOR EACH ROW EXECUTE FUNCTION log_sensitive_modification();

CREATE TRIGGER audit_learned_workflows
    AFTER INSERT OR UPDATE OR DELETE ON learned_workflows
    FOR EACH ROW EXECUTE FUNCTION log_sensitive_modification();

CREATE TRIGGER audit_agent_long_term_memory
    AFTER INSERT OR UPDATE OR DELETE ON agent_long_term_memory
    FOR EACH ROW EXECUTE FUNCTION log_sensitive_modification();


-- =============================================================================
-- BULK ACCESS DETECTION
-- =============================================================================
-- Alerts on unusual bulk data access patterns (potential exfiltration).

CREATE OR REPLACE FUNCTION detect_bulk_access()
RETURNS TRIGGER AS $$
DECLARE
    recent_reads INT;
    threshold INT := 100;  -- Alert if >100 reads in 10 minutes
BEGIN
    SELECT COUNT(*) INTO recent_reads
    FROM audit_log
    WHERE user_id = auth.uid()::text
    AND action = 'READ'
    AND resource_type = TG_TABLE_NAME
    AND timestamp > NOW() - INTERVAL '10 minutes';

    IF recent_reads > threshold THEN
        INSERT INTO audit_log (
            user_id, action, resource_type, details, risk_level, compliance_relevant
        ) VALUES (
            auth.uid()::text,
            'BULK_ACCESS_ALERT',
            TG_TABLE_NAME,
            jsonb_build_object(
                'read_count', recent_reads,
                'threshold', threshold,
                'time_window', '10 minutes'
            ),
            'CRITICAL',
            TRUE
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =============================================================================
-- AUDIT LOG RETENTION POLICY
-- =============================================================================
-- Kenya Mining Act requires 7-year retention for compliance-relevant logs.
-- Non-compliance logs can be archived after 90 days.

CREATE OR REPLACE FUNCTION archive_old_audit_logs()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Delete non-compliance logs older than 90 days
    DELETE FROM audit_log
    WHERE compliance_relevant = FALSE
    AND timestamp < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS archived_count = ROW_COUNT;

    -- Compliance logs are kept for 7 years (no deletion)
    -- In production: move to cold storage after 1 year

    RETURN archived_count;
END;
$$;


-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

-- Find similar analyses by embedding cosine distance
CREATE OR REPLACE FUNCTION find_similar_analyses(
    query_embedding vector(384),
    match_count INTEGER DEFAULT 10,
    match_threshold FLOAT DEFAULT 0.7,
    filter_mineral TEXT DEFAULT NULL,
    filter_region TEXT DEFAULT NULL
)
RETURNS TABLE (
    analysis_id TEXT,
    similarity FLOAT,
    mineral_type TEXT,
    confidence_score NUMERIC,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ah.analysis_id,
        1 - (ah.embedding <=> query_embedding) AS similarity,
        ah.mineral_type,
        ah.confidence_score,
        ah.created_at
    FROM analysis_history ah
    WHERE
        ah.embedding IS NOT NULL
        AND (1 - (ah.embedding <=> query_embedding)) >= match_threshold
        AND (filter_mineral IS NULL OR ah.mineral_type = filter_mineral)
        AND (filter_region IS NULL OR ah.location->>'region' = filter_region)
    ORDER BY ah.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Find relevant geological knowledge
CREATE OR REPLACE FUNCTION find_relevant_knowledge(
    query_embedding vector(384),
    match_count INTEGER DEFAULT 5,
    filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
    knowledge_id TEXT,
    similarity FLOAT,
    category TEXT,
    title TEXT,
    description TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        gk.knowledge_id,
        1 - (gk.embedding <=> query_embedding) AS similarity,
        gk.category,
        gk.title,
        gk.description
    FROM geological_knowledge gk
    WHERE
        gk.embedding IS NOT NULL
        AND (filter_category IS NULL OR gk.category = filter_category)
    ORDER BY gk.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

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

-- Get memory usage stats (for monitoring free tier budget)
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
