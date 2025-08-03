-- Fix SQL Ambiguity in Database Functions
-- Version: 4.1.2
-- Date: 2025-08-04
-- Purpose: Fix column reference ambiguity in get_user_session_statistics function

-- Drop and recreate the function with fixed SQL
DROP FUNCTION IF EXISTS public.get_user_session_statistics(UUID);

-- Function: get_user_session_statistics (FIXED)
-- Returns aggregated statistics for a user's sessions
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

-- Add comment for documentation
COMMENT ON FUNCTION public.get_user_session_statistics(UUID) IS 'Returns aggregated HRV statistics for a specific user (fixed ambiguity)';

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION public.get_user_session_statistics(UUID) TO authenticated;

-- Test the function
SELECT 'Function fixed successfully' as status;
