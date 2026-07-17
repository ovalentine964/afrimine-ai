-- AfriMine AI — Database Schema
-- Supabase (PostgreSQL 15+)
-- Run: supabase db push

-- ═══════════════════════════════════════════════════════════
-- EXTENSIONS
-- ═══════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- fuzzy text search

-- ═══════════════════════════════════════════════════════════
-- ENUMS
-- ═══════════════════════════════════════════════════════════

CREATE TYPE user_role AS ENUM ('miner', 'geologist', 'investor', 'admin');
CREATE TYPE sample_status AS ENUM ('pending', 'analyzing', 'completed', 'failed');
CREATE TYPE analysis_type AS ENUM ('visual', 'xrf', 'satellite', 'combined');
CREATE TYPE report_status AS ENUM ('draft', 'generated', 'reviewed', 'approved', 'filed');
CREATE TYPE sync_status AS ENUM ('pending', 'syncing', 'completed', 'failed', 'conflict');
CREATE TYPE mineral_type AS ENUM (
    'gold', 'copper', 'titanium', 'coltan', 'manganese',
    'iron_ore', 'limestone', 'gypsum', 'soda_ash',
    'fluorspar', 'diatomite', 'other'
);

-- ═══════════════════════════════════════════════════════════
-- TABLES
-- ═══════════════════════════════════════════════════════════

-- ── Users ────────────────────────────────────────────────
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_id     UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT UNIQUE,
    phone       TEXT,
    full_name   TEXT NOT NULL,
    role        user_role NOT NULL DEFAULT 'miner',
    county      TEXT,                          -- Kenyan county
    sub_county  TEXT,
    language    TEXT DEFAULT 'en',             -- en, sw, luo, etc.
    avatar_url  TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Mine Sites ───────────────────────────────────────────
CREATE TABLE mine_sites (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    county      TEXT NOT NULL,
    sub_county  TEXT,
    location    GEOGRAPHY(POINT, 4326) NOT NULL,  -- PostGIS point
    area_sqm    NUMERIC,
    license_no  TEXT,
    license_expiry DATE,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Samples ──────────────────────────────────────────────
CREATE TABLE samples (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),
    mine_site_id    UUID REFERENCES mine_sites(id),
    status          sample_status NOT NULL DEFAULT 'pending',

    -- Location
    location        GEOGRAPHY(POINT, 4326) NOT NULL,
    gps_accuracy_m  NUMERIC,
    elevation_m     NUMERIC,

    -- Sample info
    sample_code     TEXT UNIQUE NOT NULL,      -- e.g., AM-2026-0001
    depth_m         NUMERIC,
    description     TEXT,
    rock_type       TEXT,
    color           TEXT,
    texture         TEXT,

    -- Images
    photo_urls      TEXT[],                    -- array of Supabase Storage URLs
    color_card_in_frame BOOLEAN DEFAULT FALSE,

    -- Field notes
    voice_note_url  TEXT,
    field_notes     TEXT,

    -- TFLite preliminary result (offline)
    tflite_result   JSONB,
    tflite_confidence NUMERIC,

    -- Sync
    client_id       TEXT,                      -- device identifier
    client_timestamp TIMESTAMPTZ,
    sync_status     sync_status DEFAULT 'pending',

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Analyses ─────────────────────────────────────────────
CREATE TABLE analyses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id       UUID NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
    analysis_type   analysis_type NOT NULL,
    model_version   TEXT,                      -- e.g., "gemini-2.5-flash"

    -- Results
    mineral_type    mineral_type,
    mineral_name    TEXT,                      -- detailed name
    confidence      NUMERIC CHECK (confidence >= 0 AND confidence <= 1),
    grade_estimate  NUMERIC,                   -- g/t for gold, % for others
    grade_unit      TEXT DEFAULT 'g/t',

    -- Detailed results
    raw_response    JSONB,                     -- full LLM response
    visual_features JSONB,                     -- color, texture, luster
    geochemistry    JSONB,                     -- pathfinder elements

    -- Agent info
    agent_name      TEXT,                      -- which CrewAI agent
    processing_ms   INTEGER,

    -- Metadata
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Reports ──────────────────────────────────────────────
CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id),
    mine_site_id    UUID REFERENCES mine_sites(id),
    status          report_status NOT NULL DEFAULT 'draft',
    report_type     TEXT NOT NULL,             -- investor, technical, regulatory

    -- Content
    title           TEXT NOT NULL,
    summary         TEXT,
    content         JSONB,                     -- structured report data
    pdf_url         TEXT,                      -- generated PDF in Storage

    -- Metadata
    sample_ids      UUID[],                    -- samples included
    total_samples   INTEGER,
    mineral_types   mineral_type[],
    estimated_value_usd NUMERIC,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Market Prices ────────────────────────────────────────
CREATE TABLE market_prices (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mineral     mineral_type NOT NULL,
    price_usd   NUMERIC NOT NULL,
    unit        TEXT NOT NULL DEFAULT 'USD/oz', -- USD/oz, USD/lb, etc.
    source      TEXT NOT NULL,                  -- metals.live, kitco, etc.
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Sync Queue (offline → cloud) ────────────────────────
CREATE TABLE sync_queue (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id),
    entity_type TEXT NOT NULL,                 -- sample, analysis, etc.
    entity_id   UUID NOT NULL,
    operation   TEXT NOT NULL,                 -- create, update, delete
    payload     JSONB NOT NULL,
    status      sync_status NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 5,
    error_message TEXT,
    client_id   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════

-- Spatial indexes (GIST for geography)
CREATE INDEX idx_mine_sites_location ON mine_sites USING GIST (location);
CREATE INDEX idx_samples_location    ON samples USING GIST (location);

-- User lookups
CREATE INDEX idx_users_auth_id   ON users (auth_id);
CREATE INDEX idx_users_phone     ON users (phone);
CREATE INDEX idx_users_email     ON users (email);

-- Sample queries
CREATE INDEX idx_samples_user_id     ON samples (user_id);
CREATE INDEX idx_samples_mine_site   ON samples (mine_site_id);
CREATE INDEX idx_samples_status      ON samples (status);
CREATE INDEX idx_samples_created_at  ON samples (created_at DESC);
CREATE INDEX idx_samples_sync_status ON samples (sync_status) WHERE sync_status != 'completed';

-- Analysis queries
CREATE INDEX idx_analyses_sample_id  ON analyses (sample_id);
CREATE INDEX idx_analyses_mineral    ON analyses (mineral_type);
CREATE INDEX idx_analyses_created_at ON analyses (created_at DESC);

-- Report queries
CREATE INDEX idx_reports_user_id     ON reports (user_id);
CREATE INDEX idx_reports_mine_site   ON reports (mine_site_id);
CREATE INDEX idx_reports_status      ON reports (status);

-- Market price lookups
CREATE INDEX idx_market_prices_mineral ON market_prices (mineral, fetched_at DESC);

-- Sync queue
CREATE INDEX idx_sync_queue_user_status ON sync_queue (user_id, status);
CREATE INDEX idx_sync_queue_pending     ON sync_queue (created_at) WHERE status = 'pending';

-- Full-text search on samples
CREATE INDEX idx_samples_description_fts ON samples USING GIN (to_tsvector('english', COALESCE(description, '') || ' ' || COALESCE(field_notes, '')));

-- ═══════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════

ALTER TABLE users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE mine_sites    ENABLE ROW LEVEL SECURITY;
ALTER TABLE samples       ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports       ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_queue    ENABLE ROW LEVEL SECURITY;

-- ── Users: own profile only ──────────────────────────────
CREATE POLICY "Users can view own profile"
    ON users FOR SELECT
    USING (auth.uid() = auth_id);

CREATE POLICY "Users can insert own profile"
    ON users FOR INSERT
    WITH CHECK (auth.uid() = auth_id);

CREATE POLICY "Users can update own profile"
    ON users FOR UPDATE
    USING (auth.uid() = auth_id)
    WITH CHECK (auth.uid() = auth_id);

CREATE POLICY "Users can delete own profile"
    ON users FOR DELETE
    USING (auth.uid() = auth_id);

CREATE POLICY "Admins can view all users"
    ON users FOR SELECT
    USING (
        EXISTS (SELECT 1 FROM users WHERE auth_id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "Admins can manage all users"
    ON users FOR ALL
    USING (
        EXISTS (SELECT 1 FROM users WHERE auth_id = auth.uid() AND role = 'admin')
    );

-- ── Mine Sites: owner or admin ───────────────────────────
CREATE POLICY "Users can view own mine sites"
    ON mine_sites FOR SELECT
    USING (owner_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can insert own mine sites"
    ON mine_sites FOR INSERT
    WITH CHECK (owner_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can update own mine sites"
    ON mine_sites FOR UPDATE
    USING (owner_id IN (SELECT id FROM users WHERE auth_id = auth.uid()))
    WITH CHECK (owner_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can delete own mine sites"
    ON mine_sites FOR DELETE
    USING (owner_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Admins can manage all mine sites"
    ON mine_sites FOR ALL
    USING (
        EXISTS (SELECT 1 FROM users WHERE auth_id = auth.uid() AND role = 'admin')
    );

-- ── Samples: owner or admin ──────────────────────────────
CREATE POLICY "Users can view own samples"
    ON samples FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can insert own samples"
    ON samples FOR INSERT
    WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can update own samples"
    ON samples FOR UPDATE
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()))
    WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can delete own samples"
    ON samples FOR DELETE
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Admins can manage all samples"
    ON samples FOR ALL
    USING (
        EXISTS (SELECT 1 FROM users WHERE auth_id = auth.uid() AND role = 'admin')
    );

-- Geologists can view all samples in their county
CREATE POLICY "Geologists can view county samples"
    ON samples FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM users u
            JOIN mine_sites ms ON ms.owner_id = u.id
            WHERE u.auth_id = auth.uid()
            AND u.role = 'geologist'
            AND ms.id = samples.mine_site_id
        )
    );

-- ── Analyses: tied to sample ownership ───────────────────
CREATE POLICY "Users can view analyses for own samples"
    ON analyses FOR SELECT
    USING (
        sample_id IN (
            SELECT id FROM samples
            WHERE user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
        )
    );

CREATE POLICY "Service role can insert analyses"
    ON analyses FOR INSERT
    WITH CHECK (TRUE);  -- backend service uses service_role key

CREATE POLICY "Service role can update analyses"
    ON analyses FOR UPDATE
    USING (TRUE)
    WITH CHECK (TRUE);  -- backend service uses service_role key

CREATE POLICY "Users can view analyses for own samples via user_id"
    ON analyses FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Admins can manage all analyses"
    ON analyses FOR ALL
    USING (
        EXISTS (SELECT 1 FROM users WHERE auth_id = auth.uid() AND role = 'admin')
    );

-- ── Reports: owner ───────────────────────────────────────
CREATE POLICY "Users can view own reports"
    ON reports FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can insert own reports"
    ON reports FOR INSERT
    WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can update own reports"
    ON reports FOR UPDATE
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()))
    WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can delete own reports"
    ON reports FOR DELETE
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Admins can manage all reports"
    ON reports FOR ALL
    USING (
        EXISTS (SELECT 1 FROM users WHERE auth_id = auth.uid() AND role = 'admin')
    );

-- ── Market Prices: public read ───────────────────────────
CREATE POLICY "Anyone can view market prices"
    ON market_prices FOR SELECT
    USING (TRUE);

CREATE POLICY "Service role can insert prices"
    ON market_prices FOR INSERT
    WITH CHECK (TRUE);

CREATE POLICY "Service role can update prices"
    ON market_prices FOR UPDATE
    USING (TRUE)
    WITH CHECK (TRUE);

CREATE POLICY "Service role can delete old prices"
    ON market_prices FOR DELETE
    USING (TRUE);

-- ── Sync Queue: own entries only ─────────────────────────
CREATE POLICY "Users can view own sync queue"
    ON sync_queue FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can insert own sync queue"
    ON sync_queue FOR INSERT
    WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can update own sync queue"
    ON sync_queue FOR UPDATE
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()))
    WITH CHECK (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

CREATE POLICY "Users can delete own sync queue"
    ON sync_queue FOR DELETE
    USING (user_id IN (SELECT id FROM users WHERE auth_id = auth.uid()));

-- ═══════════════════════════════════════════════════════════
-- FUNCTIONS
-- ═══════════════════════════════════════════════════════════

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_mine_sites_updated_at
    BEFORE UPDATE ON mine_sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_samples_updated_at
    BEFORE UPDATE ON samples
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Generate sample codes: AM-YYYY-NNNN
-- Uses a sequence to prevent race conditions on concurrent inserts
CREATE SEQUENCE IF NOT EXISTS sample_code_seq START 1;

CREATE OR REPLACE FUNCTION generate_sample_code()
RETURNS TRIGGER AS $$
DECLARE
    next_num INTEGER;
BEGIN
    -- Use sequence to guarantee uniqueness under concurrent inserts
    SELECT nextval('sample_code_seq') INTO next_num;
    NEW.sample_code := 'AM-' || EXTRACT(YEAR FROM NOW()) || '-' || LPAD(next_num::TEXT, 4, '0');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_samples_generate_code
    BEFORE INSERT ON samples
    FOR EACH ROW
    WHEN (NEW.sample_code IS NULL)
    EXECUTE FUNCTION generate_sample_code();

-- Find samples near a point (within radius in meters)
CREATE OR REPLACE FUNCTION find_nearby_samples(
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    radius_m INTEGER DEFAULT 5000
)
RETURNS SETOF samples AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM samples
    WHERE ST_DWithin(
        location,
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)::GEOGRAPHY,
        radius_m
    )
    ORDER BY ST_Distance(
        location,
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)::GEOGRAPHY
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- ═══════════════════════════════════════════════════════════
-- VIEWS
-- ═══════════════════════════════════════════════════════════

-- Sample summary with latest analysis
CREATE VIEW sample_summary AS
SELECT
    s.id,
    s.sample_code,
    s.status,
    s.location,
    s.created_at,
    u.full_name AS collector_name,
    ms.name AS mine_site_name,
    ms.county,
    la.mineral_type,
    la.confidence,
    la.grade_estimate
FROM samples s
JOIN users u ON s.user_id = u.id
LEFT JOIN mine_sites ms ON s.mine_site_id = ms.id
LEFT JOIN LATERAL (
    SELECT mineral_type, confidence, grade_estimate
    FROM analyses
    WHERE sample_id = s.id
    ORDER BY created_at DESC
    LIMIT 1
) la ON TRUE;
