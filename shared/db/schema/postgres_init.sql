-- PostgreSQL initialization script for welfare policy keyword search
-- This script creates the schema for hybrid search (keyword + vector)

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For trigram similarity search
CREATE EXTENSION IF NOT EXISTS unaccent; -- For accent-insensitive search

-- Welfare policies table (for keyword search)
CREATE TABLE IF NOT EXISTS welfare_policies (
    id SERIAL PRIMARY KEY,
    policy_id VARCHAR(50) UNIQUE NOT NULL,

    -- Basic information
    title TEXT NOT NULL,
    ministry TEXT,
    summary TEXT,
    source_type VARCHAR(20) CHECK (source_type IN ('central', 'regional')),

    -- Regional information (for filtering)
    ctpv_nm VARCHAR(50),  -- Province/City (시도명)
    sgg_nm VARCHAR(50),   -- District (시군구명)

    -- Life cycle and themes (for filtering)
    life_cycles TEXT[],      -- Array of life cycles (영유아, 아동, 청년, etc.)
    interest_themes TEXT[],  -- Array of interest themes (서민금융, 주거, etc.)

    -- Support information
    support_cycle VARCHAR(50),     -- 지원주기
    support_provision VARCHAR(50), -- 서비스제공방식
    support_content TEXT,          -- 지원내용 (상세)

    -- Target information
    target_group VARCHAR(100),     -- 대상 그룹
    target_detail TEXT,            -- 지원대상 상세
    selection_criteria TEXT,       -- 선정기준

    -- Application information
    application_method VARCHAR(50),  -- 신청방법 유형
    application_detail TEXT,         -- 신청방법 상세

    -- Contact information
    phone VARCHAR(50),
    website TEXT,

    -- Full-text search column
    search_text TEXT,  -- Combined text for full-text search
    search_vector TSVECTOR,  -- Pre-computed search vector

    -- Metadata
    start_date DATE,
    end_date DATE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for fast keyword search
CREATE INDEX IF NOT EXISTS idx_policy_id ON welfare_policies(policy_id);
CREATE INDEX IF NOT EXISTS idx_region ON welfare_policies(ctpv_nm, sgg_nm);
CREATE INDEX IF NOT EXISTS idx_life_cycles ON welfare_policies USING GIN(life_cycles);
CREATE INDEX IF NOT EXISTS idx_interest_themes ON welfare_policies USING GIN(interest_themes);
CREATE INDEX IF NOT EXISTS idx_source_type ON welfare_policies(source_type);
CREATE INDEX IF NOT EXISTS idx_title_trgm ON welfare_policies USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_search_vector ON welfare_policies USING GIN(search_vector);

-- Function to update search_vector automatically
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('simple', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.summary, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.target_detail, '')), 'C') ||
        setweight(to_tsvector('simple', COALESCE(NEW.support_content, '')), 'C') ||
        setweight(to_tsvector('simple', COALESCE(NEW.application_detail, '')), 'D');

    -- Update search_text for debugging
    NEW.search_text := CONCAT_WS(' ',
        NEW.title,
        NEW.summary,
        NEW.target_detail,
        NEW.selection_criteria,
        NEW.support_content,
        NEW.application_detail
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update search_vector on insert/update
CREATE TRIGGER trigger_update_search_vector
BEFORE INSERT OR UPDATE ON welfare_policies
FOR EACH ROW
EXECUTE FUNCTION update_search_vector();

-- Create materialized view for common searches (optional optimization)
CREATE MATERIALIZED VIEW IF NOT EXISTS welfare_policies_by_region AS
SELECT
    ctpv_nm,
    sgg_nm,
    COUNT(*) as policy_count,
    array_agg(DISTINCT unnest(life_cycles)) as all_life_cycles,
    array_agg(DISTINCT unnest(interest_themes)) as all_themes
FROM welfare_policies
WHERE ctpv_nm IS NOT NULL
GROUP BY ctpv_nm, sgg_nm;

CREATE INDEX IF NOT EXISTS idx_mv_region ON welfare_policies_by_region(ctpv_nm, sgg_nm);

-- Grant permissions (if needed for specific user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO welfare_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO welfare_user;

-- Insert sample data for testing (optional - remove in production)
-- This will be populated by the batch job in production
