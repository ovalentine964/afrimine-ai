-- Migration 001: Initial Schema
-- Run this first to create all base tables.
-- Idempotent: uses CREATE TABLE IF NOT EXISTS.

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Short-term memory: agent sessions
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id        TEXT PRIMARY KEY,
    pipeline_run_id   TEXT NOT NULL,
    user_id           TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'paused', 'completed', 'failed', 'expired', 'consolidated')),
    current_agent     TEXT,
    agents_completed  TEXT[] DEFAULT '{}',
    state             JSONB NOT NULL DEFAULT '{}',
    state_version     INTEGER NOT NULL DEFAULT 1,
    checkpoint_id     TEXT,
    checkpoint_data   JSONB,
    parent_checkpoint TEXT,
    location          JSONB,
    mineral_type      TEXT,
    priority          TEXT DEFAULT 'normal'
                      CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    completed_at      TIMESTAMPTZ
);

-- Episodic memory: analysis history
CREATE TABLE IF NOT EXISTS analysis_history (
    analysis_id       TEXT PRIMARY KEY,
    session_id        TEXT REFERENCES agent_sessions(session_id) ON DELETE SET NULL,
    user_id           TEXT NOT NULL,
    location          JSONB NOT NULL,
    sample_data       JSONB NOT NULL,
    mineral_type      TEXT,
    sample_count      INTEGER DEFAULT 1,
    sampling_output   JSONB,
    analysis_output   JSONB,
    geology_output    JSONB,
    market_output     JSONB,
    report_output     JSONB,
    compliance_output JSONB,
    detected_minerals TEXT[],
    estimated_grade   NUMERIC,
    grade_unit        TEXT,
    confidence_score  NUMERIC CHECK (confidence_score >= 0 AND confidence_score <= 1),
    estimated_value   NUMERIC,
    value_currency    TEXT DEFAULT 'USD',
    data_quality      TEXT DEFAULT 'preliminary'
                      CHECK (data_quality IN ('preliminary', 'indicated', 'inferred', 'measured')),
    validation_status TEXT DEFAULT 'pending'
                      CHECK (validation_status IN ('pending', 'validated', 'rejected', 'needs_review')),
    embedding         vector(384),
    pipeline_duration_ms  INTEGER,
    agents_used       TEXT[] DEFAULT '{}',
    model_used        TEXT DEFAULT 'gemini-2.5-flash',
    is_anomalous      BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Semantic memory: geological knowledge
CREATE TABLE IF NOT EXISTS geological_knowledge (
    knowledge_id      TEXT PRIMARY KEY,
    category          TEXT NOT NULL
                      CHECK (category IN (
                          'deposit_model', 'pathfinder_element', 'alteration_signature',
                          'tectonic_setting', 'mineral_association', 'grade_threshold',
                          'exploration_indicator', 'regulatory_rule', 'processing_method',
                          'geological_region'
                      )),
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    content           JSONB NOT NULL,
    related_minerals  TEXT[],
    related_regions   TEXT[],
    related_deposit_models TEXT[],
    parent_knowledge  TEXT REFERENCES geological_knowledge(knowledge_id),
    confidence        NUMERIC DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),
    source            TEXT,
    source_url        TEXT,
    verified          BOOLEAN DEFAULT FALSE,
    embedding         vector(384),
    times_referenced  INTEGER DEFAULT 0,
    last_referenced   TIMESTAMPTZ,
    usefulness_score  NUMERIC DEFAULT 0.5,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Semantic memory: discovered patterns
CREATE TABLE IF NOT EXISTS mineral_patterns (
    pattern_id        TEXT PRIMARY KEY,
    pattern_type      TEXT NOT NULL
                      CHECK (pattern_type IN (
                          'element_correlation', 'grade_distribution', 'spatial_cluster',
                          'alteration_pattern', 'depth_indicator', 'economic_threshold',
                          'failure_pattern'
                      )),
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    conditions        JSONB NOT NULL,
    support_count     INTEGER NOT NULL DEFAULT 0,
    confidence        NUMERIC NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    lift              NUMERIC,
    applicable_regions TEXT[],
    applicable_deposit_models TEXT[],
    supporting_analyses TEXT[],
    contradicting_analyses TEXT[],
    status            TEXT DEFAULT 'proposed'
                      CHECK (status IN ('proposed', 'validated', 'deprecated', 'under_review')),
    validated_by      TEXT,
    embedding         vector(384),
    first_observed    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated    TIMESTAMPTZ
);

-- Procedural memory: learned workflows
CREATE TABLE IF NOT EXISTS learned_workflows (
    workflow_id       TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    workflow_type     TEXT NOT NULL
                      CHECK (workflow_type IN (
                          'full_pipeline', 'analysis_template', 'error_recovery',
                          'optimization', 'validation_check', 'agent_sequence'
                      )),
    graph_definition  JSONB NOT NULL,
    applicable_minerals TEXT[],
    applicable_regions  TEXT[],
    required_agents     TEXT[] NOT NULL,
    optional_agents     TEXT[] DEFAULT '{}',
    avg_duration_ms   INTEGER,
    success_rate      NUMERIC CHECK (success_rate >= 0 AND success_rate <= 1),
    avg_confidence    NUMERIC,
    times_used        INTEGER DEFAULT 0,
    last_used         TIMESTAMPTZ,
    source_analysis   TEXT REFERENCES analysis_history(analysis_id),
    status            TEXT DEFAULT 'active'
                      CHECK (status IN ('active', 'deprecated', 'experimental')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Long-term memory: persistent facts
CREATE TABLE IF NOT EXISTS agent_long_term_memory (
    memory_id         TEXT PRIMARY KEY,
    namespace         TEXT NOT NULL,
    key               TEXT NOT NULL,
    value             JSONB NOT NULL,
    category          TEXT,
    confidence        NUMERIC DEFAULT 1.0,
    source            TEXT,
    expires_at        TIMESTAMPTZ,
    superseded_by     TEXT REFERENCES agent_long_term_memory(memory_id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (namespace, key)
);

-- LangGraph checkpoint tables
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

-- Sync tracking
CREATE TABLE IF NOT EXISTS sync_log (
    sync_id           TEXT PRIMARY KEY,
    device_id         TEXT NOT NULL,
    entity_type       TEXT NOT NULL,
    entity_id         TEXT NOT NULL,
    action            TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    direction         TEXT NOT NULL CHECK (direction IN ('upload', 'download')),
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    conflict          BOOLEAN DEFAULT FALSE,
    resolution        TEXT CHECK (resolution IS NULL OR resolution IN ('server_wins', 'client_wins', 'merged'))
);

-- Trigger for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sessions_updated
    BEFORE UPDATE ON agent_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_analysis_updated
    BEFORE UPDATE ON analysis_history
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_knowledge_updated
    BEFORE UPDATE ON geological_knowledge
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_patterns_updated
    BEFORE UPDATE ON mineral_patterns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_workflows_updated
    BEFORE UPDATE ON learned_workflows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_ltm_updated
    BEFORE UPDATE ON agent_long_term_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
