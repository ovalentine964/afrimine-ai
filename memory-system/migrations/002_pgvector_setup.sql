-- Migration 002: pgvector Setup
-- Creates vector indexes and search functions.
-- Requires: pgvector extension enabled in Supabase.

-- Enable pgvector (run in Supabase SQL Editor if not already enabled)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- Vector similarity indexes (IVFFlat for <100K rows)
-- Switch to HNSW when row count exceeds 100K for better performance.

-- Analysis history: cosine similarity search
CREATE INDEX IF NOT EXISTS idx_analysis_embedding
    ON analysis_history USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Geological knowledge: cosine similarity search
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON geological_knowledge USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

-- Mineral patterns: cosine similarity search
CREATE INDEX IF NOT EXISTS idx_patterns_embedding
    ON mineral_patterns USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 5);

-- Function: find similar analyses by embedding
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

-- Function: find relevant geological knowledge
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

-- Function: search patterns by embedding
CREATE OR REPLACE FUNCTION search_patterns(
    query_embedding vector(384),
    match_count INTEGER DEFAULT 5
)
RETURNS TABLE (
    pattern_id TEXT,
    pattern_type TEXT,
    name TEXT,
    description TEXT,
    confidence NUMERIC,
    support_count INTEGER,
    applicable_regions TEXT[],
    status TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        mp.pattern_id,
        mp.pattern_type,
        mp.name,
        mp.description,
        mp.confidence,
        mp.support_count,
        mp.applicable_regions,
        mp.status,
        1 - (mp.embedding <=> query_embedding) AS similarity
    FROM mineral_patterns mp
    WHERE mp.embedding IS NOT NULL
    ORDER BY mp.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
