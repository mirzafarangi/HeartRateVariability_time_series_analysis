-- Add Aggregated Sleep Events View for Trend Analysis
-- Version: 1.0.0
-- Date: 2025-08-07
-- Purpose: Support sleep event aggregated trend plotting per polish_architecture.md

-- Create aggregated sleep events view
CREATE OR REPLACE VIEW aggregated_sleep_events AS
SELECT
  user_id,
  event_id,
  MIN(recorded_at) AS event_start,
  MAX(recorded_at) AS event_end,
  AVG(rmssd) AS avg_rmssd,
  COUNT(*) AS interval_count,
  STDDEV(rmssd) AS rmssd_stddev
FROM sessions
WHERE tag = 'sleep' AND event_id > 0
GROUP BY user_id, event_id
ORDER BY user_id, event_id;

-- Grant permissions to authenticated users
GRANT SELECT ON aggregated_sleep_events TO authenticated;

-- Add RLS policy for the view
ALTER VIEW aggregated_sleep_events OWNER TO postgres;
