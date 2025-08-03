-- Missing Database Functions for HRV API
-- Version: 4.1.1
-- Date: 2025-08-04
-- Purpose: Add missing PostgreSQL functions that API expects

-- Function: get_user_session_statistics
-- Returns aggregated statistics for a user's sessions
CREATE OR REPLACE FUNCTION public.get_user_session_statistics(user_uuid UUID)
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
        jsonb_object_agg(s.tag, tag_count) as tags_summary
    FROM public.sessions s
    LEFT JOIN (
        SELECT user_id, tag, COUNT(*) as tag_count
        FROM public.sessions 
        WHERE user_id = user_uuid
        GROUP BY user_id, tag
    ) tag_stats ON s.user_id = tag_stats.user_id AND s.tag = tag_stats.tag
    WHERE s.user_id = user_uuid
    GROUP BY s.user_id;
END;
$$;

-- Function: get_recent_user_sessions  
-- Returns recent sessions for a user with pagination
CREATE OR REPLACE FUNCTION public.get_recent_user_sessions(
    user_uuid UUID, 
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
    WHERE s.user_id = user_uuid
    ORDER BY s.recorded_at DESC
    LIMIT session_limit
    OFFSET session_offset;
END;
$$;

-- Add comments for documentation
COMMENT ON FUNCTION public.get_user_session_statistics(UUID) IS 'Returns aggregated HRV statistics for a specific user';
COMMENT ON FUNCTION public.get_recent_user_sessions(UUID, INTEGER, INTEGER) IS 'Returns recent sessions for a user with pagination support';

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION public.get_user_session_statistics(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_recent_user_sessions(UUID, INTEGER, INTEGER) TO authenticated;

-- Verify functions were created
SELECT 
    routine_name, 
    routine_type,
    data_type
FROM information_schema.routines 
WHERE routine_schema = 'public' 
    AND routine_name IN ('get_user_session_statistics', 'get_recent_user_sessions')
ORDER BY routine_name;
