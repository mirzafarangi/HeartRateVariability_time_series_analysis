-- HRV App - FINAL COMPREHENSIVE DATABASE SCHEMA
-- Version: 4.2.0 ULTIMATE
-- Date: 2025-08-04
-- Status: PRODUCTION READY - SINGLE SOURCE OF TRUTH
-- 
-- This file consolidates ALL schema changes, migrations, and fixes:
-- - Original schema.md structure
-- - Individual HRV metric columns (migrate_schema.sql)
-- - Database functions (add_missing_functions.sql)
-- - SQL ambiguity fixes (fix_function_ambiguity.sql)
-- 
-- USE THIS FILE FOR ALL FUTURE DATABASE SETUP AND DEPLOYMENT

-- =============================================================================
-- 1. ENABLE REQUIRED EXTENSIONS
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable Row Level Security
ALTER DATABASE postgres SET row_security = on;

-- =============================================================================
-- 2. PROFILES TABLE (User Management)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add RLS policies for profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can only see and edit their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- =============================================================================
-- 3. SESSIONS TABLE (Unified Raw + Processed HRV Data)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.sessions (
    -- Core identifiers
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session metadata (UNIFIED SCHEMA)
    tag VARCHAR(50) NOT NULL,           -- rest, sleep, experiment_paired_pre, etc.
    subtag VARCHAR(100) NOT NULL,       -- rest_single, sleep_interval_1, etc.
    event_id INTEGER NOT NULL DEFAULT 0, -- 0 = no grouping, >0 = grouped
    
    -- Timing
    duration_minutes INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Raw data
    rr_intervals DECIMAL[] NOT NULL,    -- Array of RR intervals in milliseconds
    rr_count INTEGER NOT NULL,
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Legacy support (keep for backward compatibility)
    sleep_event_id INTEGER,
    hrv_metrics JSONB,
    
    -- Individual HRV metrics (FINAL SCHEMA - v4.1.0+)
    mean_hr NUMERIC(6,2),              -- Mean heart rate in BPM
    mean_rr NUMERIC(8,2),              -- Mean RR interval in ms
    count_rr INTEGER,                  -- Total count of RR intervals
    rmssd NUMERIC(8,2),                -- Root Mean Square of Successive Differences (ms)
    sdnn NUMERIC(8,2),                 -- Standard Deviation of NN intervals (ms)
    pnn50 NUMERIC(6,2),                -- Percentage of NN intervals > 50ms different
    cv_rr NUMERIC(6,2),                -- Coefficient of Variation of RR intervals
    defa NUMERIC(6,3),                 -- Detrended Fluctuation Analysis Alpha1
    sd2_sd1 NUMERIC(6,3),              -- Poincaré plot SD2/SD1 ratio
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_tag CHECK (tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout')),
    CONSTRAINT valid_event_id CHECK (event_id >= 0),
    CONSTRAINT valid_duration CHECK (duration_minutes > 0),
    CONSTRAINT valid_rr_count CHECK (rr_count > 0)
);

-- Add RLS policies for sessions
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

-- Users can only access their own sessions
CREATE POLICY "Users can view own sessions" ON public.sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions" ON public.sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" ON public.sessions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sessions" ON public.sessions
    FOR DELETE USING (auth.uid() = user_id);

-- =============================================================================
-- 4. PERFORMANCE INDEXES
-- =============================================================================

-- Primary performance indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_tag ON public.sessions(user_id, tag);
CREATE INDEX IF NOT EXISTS idx_sessions_event_id ON public.sessions(event_id) WHERE event_id > 0;
CREATE INDEX IF NOT EXISTS idx_sessions_status ON public.sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_recorded_at ON public.sessions(recorded_at);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sessions_user_event ON public.sessions(user_id, event_id) WHERE event_id > 0;
CREATE INDEX IF NOT EXISTS idx_sessions_tag_status ON public.sessions(tag, status);

-- HRV metrics performance index (added in v4.1.0)
CREATE INDEX IF NOT EXISTS idx_sessions_hrv_metrics 
ON public.sessions (user_id, mean_hr, rmssd, sdnn) 
WHERE mean_hr IS NOT NULL;

-- Sleep event index (for legacy support)
CREATE INDEX IF NOT EXISTS idx_sessions_sleep_event ON public.sessions(sleep_event_id) WHERE sleep_event_id IS NOT NULL;

-- =============================================================================
-- 5. DATABASE FUNCTIONS (API Support)
-- =============================================================================

-- Function: get_user_session_statistics
-- Returns aggregated statistics for a user's sessions
-- Fixed SQL ambiguity in v4.1.2
CREATE OR REPLACE FUNCTION public.get_user_session_statistics(target_user_id UUID)
RETURNS TABLE (
    user_id UUID,
    total_sessions INTEGER,
    total_duration_minutes INTEGER,
    avg_rmssd NUMERIC,
    avg_sdnn NUMERIC,
    avg_mean_hr NUMERIC,
    latest_session_date TIMESTAMP WITH TIME ZONE,
    tags_summary JSONB
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.user_id,
        COUNT(*)::INTEGER as total_sessions,
        SUM(s.duration_minutes)::INTEGER as total_duration_minutes,
        AVG(s.rmssd) as avg_rmssd,
        AVG(s.sdnn) as avg_sdnn,
        AVG(s.mean_hr) as avg_mean_hr,
        MAX(s.recorded_at) as latest_session_date,
        jsonb_object_agg(s.tag, tag_counts.tag_count) as tags_summary
    FROM public.sessions s
    LEFT JOIN (
        SELECT s2.tag, COUNT(*) as tag_count
        FROM public.sessions s2
        WHERE s2.user_id = target_user_id
        GROUP BY s2.tag
    ) tag_counts ON s.tag = tag_counts.tag
    WHERE s.user_id = target_user_id
    GROUP BY s.user_id;
END;
$$;

-- Function: get_recent_user_sessions  
-- Returns recent sessions for a user with pagination
CREATE OR REPLACE FUNCTION public.get_recent_user_sessions(
    target_user_id UUID, 
    session_limit INTEGER DEFAULT 20,
    session_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    session_id UUID,
    user_id UUID,
    tag VARCHAR,
    subtag VARCHAR,
    event_id INTEGER,
    duration_minutes INTEGER,
    recorded_at TIMESTAMP WITH TIME ZONE,
    rr_count INTEGER,
    status VARCHAR,
    processed_at TIMESTAMP WITH TIME ZONE,
    mean_hr NUMERIC,
    mean_rr NUMERIC,
    count_rr INTEGER,
    rmssd NUMERIC,
    sdnn NUMERIC,
    pnn50 NUMERIC,
    cv_rr NUMERIC,
    defa NUMERIC,
    sd2_sd1 NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.session_id,
        s.user_id,
        s.tag,
        s.subtag,
        s.event_id,
        s.duration_minutes,
        s.recorded_at,
        s.rr_count,
        s.status,
        s.processed_at,
        s.mean_hr,
        s.mean_rr,
        s.count_rr,
        s.rmssd,
        s.sdnn,
        s.pnn50,
        s.cv_rr,
        s.defa,
        s.sd2_sd1,
        s.created_at,
        s.updated_at
    FROM public.sessions s
    WHERE s.user_id = target_user_id
    ORDER BY s.recorded_at DESC
    LIMIT session_limit
    OFFSET session_offset;
END;
$$;

-- =============================================================================
-- 6. TRIGGERS AND AUTOMATION
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for sessions table
CREATE TRIGGER update_sessions_updated_at 
    BEFORE UPDATE ON public.sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION public.update_updated_at_column();

-- Trigger for profiles table
CREATE TRIGGER update_profiles_updated_at 
    BEFORE UPDATE ON public.profiles 
    FOR EACH ROW 
    EXECUTE FUNCTION public.update_updated_at_column();

-- =============================================================================
-- 7. PERMISSIONS AND SECURITY
-- =============================================================================

-- Grant permissions to authenticated users
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON public.profiles TO authenticated;
GRANT ALL ON public.sessions TO authenticated;

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION public.get_user_session_statistics(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_recent_user_sessions(UUID, INTEGER, INTEGER) TO authenticated;

-- =============================================================================
-- 8. COMMENTS AND DOCUMENTATION
-- =============================================================================

-- Table comments
COMMENT ON TABLE public.profiles IS 'User profiles extending Supabase auth.users';
COMMENT ON TABLE public.sessions IS 'Unified HRV session data (raw + processed)';

-- Column comments for sessions table
COMMENT ON COLUMN public.sessions.session_id IS 'Unique session identifier';
COMMENT ON COLUMN public.sessions.user_id IS 'Reference to auth.users(id)';
COMMENT ON COLUMN public.sessions.tag IS 'Base session type (rest, sleep, etc.)';
COMMENT ON COLUMN public.sessions.subtag IS 'Specific session subtype (auto-assigned)';
COMMENT ON COLUMN public.sessions.event_id IS 'Event grouping ID (0=standalone, >0=grouped)';
COMMENT ON COLUMN public.sessions.rr_intervals IS 'Array of RR intervals in milliseconds';
COMMENT ON COLUMN public.sessions.mean_hr IS 'Mean heart rate in beats per minute';
COMMENT ON COLUMN public.sessions.mean_rr IS 'Mean RR interval in milliseconds';
COMMENT ON COLUMN public.sessions.count_rr IS 'Total count of RR intervals';
COMMENT ON COLUMN public.sessions.rmssd IS 'Root Mean Square of Successive Differences (ms)';
COMMENT ON COLUMN public.sessions.sdnn IS 'Standard Deviation of NN intervals (ms)';
COMMENT ON COLUMN public.sessions.pnn50 IS 'Percentage of NN intervals > 50ms different';
COMMENT ON COLUMN public.sessions.cv_rr IS 'Coefficient of Variation of RR intervals';
COMMENT ON COLUMN public.sessions.defa IS 'Detrended Fluctuation Analysis Alpha1';
COMMENT ON COLUMN public.sessions.sd2_sd1 IS 'Poincaré plot SD2/SD1 ratio';

-- Function comments
COMMENT ON FUNCTION public.get_user_session_statistics(UUID) IS 'Returns aggregated HRV statistics for a specific user (v4.1.2 - fixed ambiguity)';
COMMENT ON FUNCTION public.get_recent_user_sessions(UUID, INTEGER, INTEGER) IS 'Returns recent sessions for a user with pagination support';

-- =============================================================================
-- 9. SCHEMA VERIFICATION
-- =============================================================================

-- Verify tables exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'profiles' AND table_schema = 'public') THEN
        RAISE EXCEPTION 'profiles table was not created';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sessions' AND table_schema = 'public') THEN
        RAISE EXCEPTION 'sessions table was not created';
    END IF;
    
    RAISE NOTICE 'Schema verification: All tables created successfully';
END $$;

-- Verify functions exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.routines WHERE routine_name = 'get_user_session_statistics' AND routine_schema = 'public') THEN
        RAISE EXCEPTION 'get_user_session_statistics function was not created';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.routines WHERE routine_name = 'get_recent_user_sessions' AND routine_schema = 'public') THEN
        RAISE EXCEPTION 'get_recent_user_sessions function was not created';
    END IF;
    
    RAISE NOTICE 'Function verification: All functions created successfully';
END $$;

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================

-- Final success message
SELECT 'HRV Database Schema v4.2.0 ULTIMATE - Deployment Complete!' as status;
