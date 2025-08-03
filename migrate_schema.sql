-- HRV Database Schema Migration
-- Add missing individual HRV metric columns to sessions table
-- Version: 4.1.0
-- Date: 2025-08-04

-- Add individual HRV metric columns to sessions table
ALTER TABLE public.sessions 
ADD COLUMN IF NOT EXISTS mean_hr NUMERIC(6,2),
ADD COLUMN IF NOT EXISTS mean_rr NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS count_rr INTEGER,
ADD COLUMN IF NOT EXISTS rmssd NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS sdnn NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS pnn50 NUMERIC(6,2),
ADD COLUMN IF NOT EXISTS cv_rr NUMERIC(6,2),
ADD COLUMN IF NOT EXISTS defa NUMERIC(6,3),
ADD COLUMN IF NOT EXISTS sd2_sd1 NUMERIC(6,3);

-- Add comments for documentation
COMMENT ON COLUMN public.sessions.mean_hr IS 'Mean heart rate in beats per minute';
COMMENT ON COLUMN public.sessions.mean_rr IS 'Mean RR interval in milliseconds';
COMMENT ON COLUMN public.sessions.count_rr IS 'Total count of RR intervals';
COMMENT ON COLUMN public.sessions.rmssd IS 'Root Mean Square of Successive Differences (ms)';
COMMENT ON COLUMN public.sessions.sdnn IS 'Standard Deviation of NN intervals (ms)';
COMMENT ON COLUMN public.sessions.pnn50 IS 'Percentage of NN intervals > 50ms different';
COMMENT ON COLUMN public.sessions.cv_rr IS 'Coefficient of Variation of RR intervals';
COMMENT ON COLUMN public.sessions.defa IS 'Detrended Fluctuation Analysis Alpha1';
COMMENT ON COLUMN public.sessions.sd2_sd1 IS 'Poincaré plot SD2/SD1 ratio';

-- Create index for performance on HRV metrics queries
CREATE INDEX IF NOT EXISTS idx_sessions_hrv_metrics 
ON public.sessions (user_id, mean_hr, rmssd, sdnn) 
WHERE mean_hr IS NOT NULL;

-- Verify the migration
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'sessions' 
    AND table_schema = 'public'
    AND column_name IN ('mean_hr', 'mean_rr', 'count_rr', 'rmssd', 'sdnn', 'pnn50', 'cv_rr', 'defa', 'sd2_sd1')
ORDER BY column_name;
