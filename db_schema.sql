-- =====================================================
-- HRV Brain Database Schema - Final Production v4.1
-- =====================================================
-- All inconsistencies fixed:
-- 1. Subtag patterns include tag prefix for paired variants
-- 2. Analytics use rr_count (not count_rr) to match table column
-- 3. RLS policies simplified (service role bypasses RLS in Supabase)
-- 4. Consistent parameter naming across all analytics functions
-- 5. Documentation updated for trigger-based allocation
-- 6. WITH CHECK clauses added to UPDATE/ALL policies for safety
-- =====================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- optional, harmless

-- ----------------------------------------------------
-- PROFILES (thin wrapper around auth.users)
-- ----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT UNIQUE,
  full_name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies for profiles
-- Note: Service role keys bypass RLS in Supabase, so no special handling needed
CREATE POLICY "Users can view own profile" ON public.profiles
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
  FOR UPDATE USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);  -- Added WITH CHECK for safety

-- ----------------------------------------------------
-- SESSIONS (the only data store you truly need)
-- ----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.sessions (
  -- identifiers
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- tagging (canonical - WITH CORRECT PREFIXES)
  tag TEXT NOT NULL,
  subtag TEXT NOT NULL,
  event_id INTEGER NOT NULL DEFAULT 0,

  -- convenience (no triggers needed)
  interval_number INTEGER GENERATED ALWAYS AS (
    CASE
      WHEN tag='sleep' AND subtag ~ '^sleep_interval_[0-9]+$'
      THEN (regexp_match(subtag, '^sleep_interval_([0-9]+)$'))[1]::int
      ELSE NULL
    END
  ) STORED,
  recorded_at TIMESTAMPTZ NOT NULL,
  recorded_date_utc DATE GENERATED ALWAYS AS ((recorded_at AT TIME ZONE 'UTC')::date) STORED,
  duration_minutes INTEGER NOT NULL,

  -- raw data
  rr_intervals DOUBLE PRECISION[] NOT NULL,
  rr_count INTEGER NOT NULL,  -- This is the correct column name

  -- metrics (9 core)
  mean_hr DOUBLE PRECISION,
  mean_rr DOUBLE PRECISION,
  rmssd DOUBLE PRECISION,
  sdnn DOUBLE PRECISION,
  pnn50 DOUBLE PRECISION,
  cv_rr DOUBLE PRECISION,
  defa DOUBLE PRECISION,
  sd2_sd1 DOUBLE PRECISION,

  -- status + stamps
  status TEXT NOT NULL DEFAULT 'completed',
  processed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- constraints (FIXED SUBTAG PATTERNS WITH PREFIXES)
  CONSTRAINT chk_tag_values CHECK (tag IN ('wake_check','pre_sleep','sleep','experiment')),
  CONSTRAINT chk_subtag_by_tag CHECK (
    (tag='wake_check' AND subtag ~ '^wake_check_(single|paired_day_pre)$') OR
    (tag='pre_sleep'  AND subtag ~ '^pre_sleep_(single|paired_day_post)$') OR
    (tag='sleep'      AND subtag ~ '^sleep_interval_[1-9][0-9]*$') OR
    (tag='experiment' AND subtag ~ '^experiment_(single|protocol_[a-z0-9_]+)$')
  ),
  CONSTRAINT chk_sleep_grouping CHECK (
    (tag <> 'sleep' AND event_id = 0) OR (tag='sleep' AND event_id >= 0)  -- Allow 0 for trigger
  ),
  CONSTRAINT chk_rr_len_matches_count CHECK (array_length(rr_intervals, 1) = rr_count),
  CONSTRAINT chk_rr_count_positive CHECK (rr_count > 0),
  CONSTRAINT chk_duration_positive CHECK (duration_minutes > 0),
  CONSTRAINT chk_metric_ranges_soft CHECK (
    (mean_hr   IS NULL OR (mean_hr > 30 AND mean_hr < 250)) AND
    (mean_rr   IS NULL OR (mean_rr > 240 AND mean_rr < 2000)) AND
    (rmssd     IS NULL OR rmssd   >= 0) AND
    (sdnn      IS NULL OR sdnn    >= 0) AND
    (pnn50     IS NULL OR (pnn50  >= 0 AND pnn50 <= 100)) AND
    (cv_rr     IS NULL OR cv_rr   >= 0) AND
    (defa      IS NULL OR (defa   >= 0 AND defa <= 2)) AND
    (sd2_sd1   IS NULL OR sd2_sd1 > 0)
  )
);

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for sessions
-- Note: Service role keys bypass RLS in Supabase, so no special handling needed
CREATE POLICY "Users can view own sessions" ON public.sessions
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions" ON public.sessions
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" ON public.sessions
  FOR UPDATE USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);  -- Added WITH CHECK for safety

CREATE POLICY "Users can delete own sessions" ON public.sessions
  FOR DELETE USING (auth.uid() = user_id);

-- keep updated_at fresh
CREATE OR REPLACE FUNCTION public.touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sessions_touch ON public.sessions;
CREATE TRIGGER trg_sessions_touch
  BEFORE UPDATE ON public.sessions
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

DROP TRIGGER IF EXISTS trg_profiles_touch ON public.profiles;
CREATE TRIGGER trg_profiles_touch
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- ----------------------------------------------------
-- Indexes (power the 5 models + fast writes)
-- ----------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sessions_user_time
  ON public.sessions (user_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_sleep_latest_event
  ON public.sessions (user_id, event_id DESC)
  WHERE tag='sleep' AND event_id > 0;

-- Per-user unique constraint (not global)
CREATE UNIQUE INDEX IF NOT EXISTS uq_sleep_interval_per_user_event
  ON public.sessions (user_id, event_id, interval_number)
  WHERE tag='sleep' AND event_id > 0 AND interval_number IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sleep_event_interval_order
  ON public.sessions (event_id, interval_number, recorded_at)
  WHERE tag='sleep' AND event_id > 0;

CREATE INDEX IF NOT EXISTS idx_pairing_by_date
  ON public.sessions (user_id, recorded_date_utc, tag)
  WHERE tag IN ('wake_check','pre_sleep');

CREATE UNIQUE INDEX IF NOT EXISTS uq_wake_pre_dedupe
  ON public.sessions (user_id, tag, recorded_at, subtag)
  WHERE tag IN ('wake_check','pre_sleep') AND event_id=0;

-- ----------------------------------------------------
-- Sleep event-id counter (for automatic allocation)
-- ----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.sleep_event_counter (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  next_event_id INTEGER NOT NULL DEFAULT 1,
  last_allocated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.sleep_event_counter ENABLE ROW LEVEL SECURITY;

-- Note: Service role keys bypass RLS in Supabase, so no special handling needed
CREATE POLICY "Users can view own counter" ON public.sleep_event_counter
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own counter" ON public.sleep_event_counter
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);  -- Added WITH CHECK for safety

-- ----------------------------------------------------
-- Event ID Allocator Function
-- Used by trigger for automatic allocation when event_id=0
-- Can also be called explicitly for backward compatibility
-- ----------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_allocate_sleep_event_id(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
  v_event_id INTEGER;
  v_lock BIGINT;
BEGIN
  -- hash user_id to a lock key
  v_lock := ('x' || left(md5(p_user_id::text), 15))::bit(60)::bigint;
  PERFORM pg_advisory_lock(v_lock);
  BEGIN
    INSERT INTO public.sleep_event_counter (user_id, next_event_id, last_allocated_at)
    VALUES (p_user_id, 2, NOW())
    ON CONFLICT (user_id) DO UPDATE
      SET next_event_id = sleep_event_counter.next_event_id + 1,
          last_allocated_at = NOW()
    RETURNING next_event_id - 1 INTO v_event_id;
    
    PERFORM pg_advisory_unlock(v_lock);
  EXCEPTION
    WHEN OTHERS THEN
      PERFORM pg_advisory_unlock(v_lock);
      RAISE;
  END;
  RETURN v_event_id;
END; $$ LANGUAGE plpgsql;

-- ----------------------------------------------------
-- Trigger Function for Auto Event ID Assignment
-- PREFERRED METHOD: Clients send event_id=0, DB auto-assigns
-- ----------------------------------------------------
CREATE OR REPLACE FUNCTION public.trg_sessions_assign_sleep_event()
RETURNS trigger AS $$
DECLARE
  v_interval INT;
  v_lock BIGINT;
  v_latest_event_id INT;
  v_latest_max_interval INT;
BEGIN
  -- Only process sleep rows
  IF NEW.tag <> 'sleep' THEN
    RETURN NEW;
  END IF;

  -- Extract interval number from subtag
  v_interval := NULLIF((regexp_match(NEW.subtag, '^sleep_interval_([0-9]+)$'))[1], '')::int;

  IF v_interval IS NULL OR v_interval < 1 THEN
    RAISE EXCEPTION 'Invalid sleep subtag (%). Expected sleep_interval_k with k>=1.', NEW.subtag
      USING ERRCODE = '22023';
  END IF;

  -- Normalize NULL to 0
  IF NEW.event_id IS NULL THEN
    NEW.event_id := 0;
  END IF;

  -- Fast path: explicit event_id > 0 is allowed (for backfill/explicit attachment)
  IF NEW.event_id > 0 THEN
    RETURN NEW;
  END IF;

  -- From here, NEW.event_id = 0 -> DB must assign/attach
  -- Use advisory lock to serialize per user
  v_lock := ('x' || left(md5(NEW.user_id::text || '::sleep_assign'), 15))::bit(60)::bigint;
  PERFORM pg_advisory_lock(v_lock);
  
  BEGIN
    IF v_interval = 1 THEN
      -- Start of a new sleep event: allocate next event_id
      NEW.event_id := public.fn_allocate_sleep_event_id(NEW.user_id);
    ELSE
      -- Attach to latest event, but ONLY if its max interval is exactly v_interval - 1
      SELECT MAX(event_id) INTO v_latest_event_id
      FROM public.sessions
      WHERE user_id = NEW.user_id AND tag = 'sleep' AND event_id > 0;

      IF v_latest_event_id IS NULL THEN
        RAISE EXCEPTION 'Cannot attach interval %: no existing sleep event. Upload sleep_interval_1 first or provide event_id.', v_interval
          USING ERRCODE = '22023';
      END IF;

      -- Check that the latest event has interval k-1
      SELECT MAX(interval_number) INTO v_latest_max_interval
      FROM public.sessions
      WHERE user_id = NEW.user_id AND tag = 'sleep' AND event_id = v_latest_event_id;

      IF COALESCE(v_latest_max_interval, 0) <> v_interval - 1 THEN
        RAISE EXCEPTION 'Out-of-order interval %: event % has max interval %, expected %.', 
          v_interval, v_latest_event_id, COALESCE(v_latest_max_interval, 0), v_interval - 1
          USING ERRCODE = '22023';
      END IF;

      NEW.event_id := v_latest_event_id;
    END IF;

    PERFORM pg_advisory_unlock(v_lock);
  EXCEPTION
    WHEN OTHERS THEN
      PERFORM pg_advisory_unlock(v_lock);
      RAISE;
  END;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- BEFORE INSERT Trigger for Sleep Event Assignment
CREATE TRIGGER trg_sessions_assign_sleep_event
BEFORE INSERT ON public.sessions
FOR EACH ROW
EXECUTE FUNCTION public.trg_sessions_assign_sleep_event();

-- ====================================================
-- 5 ANALYTICS FUNCTIONS (FIXED - CONSISTENT PARAMETERS)
-- All use p_window for windowing parameter (not p_points/p_events)
-- All use rr_count (not count_rr) to match table column
-- ====================================================

-- 1) Baseline (wake_check) - FIXED PARAMETER NAME
CREATE OR REPLACE FUNCTION public.fn_baseline_points(
  p_user_id UUID,
  p_metric TEXT DEFAULT 'rmssd',
  p_window INTEGER DEFAULT 7  -- Changed from p_points to p_window for consistency
)
RETURNS TABLE(
  t TIMESTAMPTZ,
  value DOUBLE PRECISION,
  rolling_avg DOUBLE PRECISION,
  rolling_sd DOUBLE PRECISION
) LANGUAGE sql STABLE AS $$
WITH base AS (
  SELECT recorded_at AS t,
         CASE p_metric
           WHEN 'rmssd' THEN rmssd
           WHEN 'sdnn' THEN sdnn
           WHEN 'sd2_sd1' THEN sd2_sd1
           WHEN 'mean_hr' THEN mean_hr
           WHEN 'mean_rr' THEN mean_rr
           WHEN 'rr_count' THEN rr_count::DOUBLE PRECISION  -- FIXED: use rr_count
           WHEN 'pnn50' THEN pnn50
           WHEN 'cv_rr' THEN cv_rr
           WHEN 'defa' THEN defa
           ELSE rmssd
         END AS v
  FROM public.sessions
  WHERE user_id = p_user_id AND tag='wake_check'
  ORDER BY recorded_at
)
SELECT t,
       v AS value,
       AVG(v) OVER (ORDER BY t ROWS BETWEEN p_window-1 PRECEDING AND CURRENT ROW) AS rolling_avg,
       STDDEV_POP(v) OVER (ORDER BY t ROWS BETWEEN p_window-1 PRECEDING AND CURRENT ROW) AS rolling_sd
FROM base
WHERE v IS NOT NULL
ORDER BY t;
$$;

-- 2) Micro Sleep (latest event intervals) - FIXED PARAMETER NAME
CREATE OR REPLACE FUNCTION public.fn_micro_sleep_points(
  p_user_id UUID,
  p_metric TEXT DEFAULT 'rmssd',
  p_window INTEGER DEFAULT 3  -- Changed from p_points to p_window
)
RETURNS TABLE(
  event_id INTEGER,
  interval_number INTEGER,
  t TIMESTAMPTZ,
  value DOUBLE PRECISION,
  rolling_avg DOUBLE PRECISION,
  rolling_sd DOUBLE PRECISION
) LANGUAGE sql STABLE AS $$
WITH latest AS (
  SELECT MAX(event_id) AS eid
  FROM public.sessions
  WHERE user_id=p_user_id AND tag='sleep' AND event_id>0
),
base AS (
  SELECT s.event_id, s.interval_number, s.recorded_at AS t,
         CASE p_metric
           WHEN 'rmssd' THEN s.rmssd
           WHEN 'sdnn' THEN s.sdnn
           WHEN 'sd2_sd1' THEN s.sd2_sd1
           WHEN 'mean_hr' THEN s.mean_hr
           WHEN 'mean_rr' THEN s.mean_rr
           WHEN 'rr_count' THEN s.rr_count::DOUBLE PRECISION  -- FIXED
           WHEN 'pnn50' THEN s.pnn50
           WHEN 'cv_rr' THEN s.cv_rr
           WHEN 'defa' THEN s.defa
           ELSE s.rmssd
         END AS v
  FROM public.sessions s, latest
  WHERE s.user_id=p_user_id AND s.tag='sleep' AND s.event_id=latest.eid
  ORDER BY s.interval_number
)
SELECT event_id, interval_number, t, v AS value,
       AVG(v) OVER (ORDER BY interval_number ROWS BETWEEN p_window-1 PRECEDING AND CURRENT ROW) AS rolling_avg,
       STDDEV_POP(v) OVER (ORDER BY interval_number ROWS BETWEEN p_window-1 PRECEDING AND CURRENT ROW) AS rolling_sd
FROM base
WHERE v IS NOT NULL
ORDER BY interval_number;
$$;

-- 3) Macro Sleep (event aggregates) - FIXED PARAMETER NAME
CREATE OR REPLACE FUNCTION public.fn_macro_sleep_points(
  p_user_id UUID,
  p_metric TEXT DEFAULT 'rmssd',
  p_window INTEGER DEFAULT 3  -- Changed from p_events to p_window
)
RETURNS TABLE(
  event_id INTEGER,
  t TIMESTAMPTZ,
  avg_value DOUBLE PRECISION,
  rolling_avg DOUBLE PRECISION
) LANGUAGE sql STABLE AS $$
WITH agg AS (
  SELECT event_id,
         MIN(recorded_at) AS t,
         AVG(
           CASE p_metric
             WHEN 'rmssd' THEN rmssd
             WHEN 'sdnn' THEN sdnn
             WHEN 'sd2_sd1' THEN sd2_sd1
             WHEN 'mean_hr' THEN mean_hr
             WHEN 'mean_rr' THEN mean_rr
             WHEN 'rr_count' THEN rr_count::DOUBLE PRECISION  -- FIXED
             WHEN 'pnn50' THEN pnn50
             WHEN 'cv_rr' THEN cv_rr
             WHEN 'defa' THEN defa
             ELSE rmssd
           END
         ) AS avg_value
  FROM public.sessions
  WHERE user_id=p_user_id AND tag='sleep' AND event_id>0
  GROUP BY event_id
)
SELECT event_id, t, avg_value,
       AVG(avg_value) OVER (ORDER BY t ROWS BETWEEN p_window-1 PRECEDING AND CURRENT ROW) AS rolling_avg
FROM agg
WHERE avg_value IS NOT NULL
ORDER BY t;
$$;

-- 4) Day Load (paired same UTC date, time window) - Parameters unchanged
CREATE OR REPLACE FUNCTION public.fn_day_load_points(
  p_user_id UUID,
  p_metric TEXT DEFAULT 'rmssd',
  p_min_hours INTEGER DEFAULT 12,
  p_max_hours INTEGER DEFAULT 18
)
RETURNS TABLE(
  day_date DATE,
  wake_ts TIMESTAMPTZ,
  pre_ts TIMESTAMPTZ,
  wake_value DOUBLE PRECISION,
  pre_value DOUBLE PRECISION,
  delta_value DOUBLE PRECISION
) LANGUAGE sql STABLE AS $$
WITH w AS (
  SELECT recorded_date_utc AS d, recorded_at AS t,
         CASE p_metric 
           WHEN 'rmssd' THEN rmssd 
           WHEN 'sdnn' THEN sdnn
           WHEN 'sd2_sd1' THEN sd2_sd1 
           WHEN 'mean_hr' THEN mean_hr
           WHEN 'mean_rr' THEN mean_rr
           WHEN 'rr_count' THEN rr_count::DOUBLE PRECISION  -- FIXED
           WHEN 'pnn50' THEN pnn50
           WHEN 'cv_rr' THEN cv_rr
           WHEN 'defa' THEN defa
           ELSE rmssd 
         END AS v
  FROM public.sessions
  WHERE user_id=p_user_id AND tag='wake_check'
),
p AS (
  SELECT recorded_date_utc AS d, recorded_at AS t,
         CASE p_metric 
           WHEN 'rmssd' THEN rmssd 
           WHEN 'sdnn' THEN sdnn
           WHEN 'sd2_sd1' THEN sd2_sd1 
           WHEN 'mean_hr' THEN mean_hr
           WHEN 'mean_rr' THEN mean_rr
           WHEN 'rr_count' THEN rr_count::DOUBLE PRECISION  -- FIXED
           WHEN 'pnn50' THEN pnn50
           WHEN 'cv_rr' THEN cv_rr
           WHEN 'defa' THEN defa
           ELSE rmssd 
         END AS v
  FROM public.sessions
  WHERE user_id=p_user_id AND tag='pre_sleep'
)
SELECT w.d AS day_date, w.t AS wake_ts, p.t AS pre_ts,
       w.v AS wake_value, p.v AS pre_value,
       (p.v - w.v) AS delta_value
FROM w JOIN p ON p.d = w.d
WHERE w.v IS NOT NULL AND p.v IS NOT NULL
  AND EXTRACT(EPOCH FROM (p.t - w.t))/3600.0 BETWEEN p_min_hours AND p_max_hours
ORDER BY day_date;
$$;

-- 5) Experiment trends - FIXED PARAMETER NAME
CREATE OR REPLACE FUNCTION public.fn_experiment_points(
  p_user_id UUID,
  p_metric TEXT DEFAULT 'rmssd',
  p_window INTEGER DEFAULT 3,  -- Changed from p_points to p_window
  p_protocol_subtag TEXT DEFAULT NULL
)
RETURNS TABLE(
  t TIMESTAMPTZ,
  value DOUBLE PRECISION,
  rolling_avg DOUBLE PRECISION
) LANGUAGE sql STABLE AS $$
WITH base AS (
  SELECT recorded_at AS t,
         CASE p_metric
           WHEN 'rmssd' THEN rmssd
           WHEN 'sdnn' THEN sdnn
           WHEN 'sd2_sd1' THEN sd2_sd1
           WHEN 'mean_hr' THEN mean_hr
           WHEN 'mean_rr' THEN mean_rr
           WHEN 'rr_count' THEN rr_count::DOUBLE PRECISION  -- FIXED
           WHEN 'pnn50' THEN pnn50
           WHEN 'cv_rr' THEN cv_rr
           WHEN 'defa' THEN defa
           ELSE rmssd
         END AS v
  FROM public.sessions
  WHERE user_id=p_user_id
    AND tag='experiment'
    AND (p_protocol_subtag IS NULL OR subtag = p_protocol_subtag)
  ORDER BY recorded_at
)
SELECT t,
       v AS value,
       AVG(v) OVER (ORDER BY t ROWS BETWEEN p_window-1 PRECEDING AND CURRENT ROW) AS rolling_avg
FROM base
WHERE v IS NOT NULL
ORDER BY t;
$$;

-- ----------------------------------------------------
-- Constraint to ensure sleep intervals have event_id > 0 after trigger
-- ----------------------------------------------------
CREATE OR REPLACE FUNCTION public.check_sleep_has_event_id()
RETURNS trigger AS $$
BEGIN
  IF NEW.tag = 'sleep' AND NEW.event_id = 0 THEN
    RAISE EXCEPTION 'Sleep session must have event_id > 0 after trigger processing'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- This runs AFTER the BEFORE trigger, as a final check
CREATE CONSTRAINT TRIGGER trg_check_sleep_event_id
AFTER INSERT ON public.sessions
FOR EACH ROW
EXECUTE FUNCTION public.check_sleep_has_event_id();

-- ----------------------------------------------------
-- Grants (with service role support)
-- ----------------------------------------------------
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles, public.sessions, public.sleep_event_counter TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION
  public.fn_allocate_sleep_event_id(UUID),
  public.fn_baseline_points(UUID, TEXT, INTEGER),
  public.fn_micro_sleep_points(UUID, TEXT, INTEGER),
  public.fn_macro_sleep_points(UUID, TEXT, INTEGER),
  public.fn_day_load_points(UUID, TEXT, INTEGER, INTEGER),
  public.fn_experiment_points(UUID, TEXT, INTEGER, TEXT)
TO authenticated, service_role;

-- =====================================================
-- Migration Notes:
-- 1. This schema uses trigger-based event_id allocation
--    Clients should send event_id=0 for sleep sessions
-- 2. The fn_allocate_sleep_event_id function is optional
--    but maintained for backward compatibility
-- 3. All analytics functions now support rr_count metric
-- 4. Parameter naming is consistent: p_window for windowing
-- 5. RLS policies support both auth.uid() and service_role
-- =====================================================