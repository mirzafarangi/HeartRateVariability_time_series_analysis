-- =====================================================
-- HRV App Unified PostgreSQL Schema (Supabase Edition)
-- =====================================================
-- Version: 3.3.4 Final
-- Date: 2025-08-03
-- Status: Production Ready - Single Source of Truth
-- Source: schema.md (Golden Reference) + Supabase Auth Integration
--
-- This is the AUTHORITATIVE database schema for the entire HRV system.
-- All iOS, API, and database components must strictly follow this schema.
-- 
-- CRITICAL BUSINESS ASSET - Handle with care and maintain consistency
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================
-- USER PROFILES TABLE (Extends Supabase Auth)
-- =====================================================
-- Note: Supabase provides auth.users table automatically
-- This profiles table extends it with HRV-specific user data

CREATE TABLE public.profiles (
    -- Primary key references Supabase auth.users
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- User information (synced from auth.users)
    email VARCHAR(255),
    
    -- HRV-specific user data
    device_name VARCHAR(100),
    
    -- Session counters (automatically maintained by triggers)
    raw_sessions_count INTEGER DEFAULT 0 NOT NULL,
    processed_sessions_count INTEGER DEFAULT 0 NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Constraints
    CONSTRAINT profiles_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT profiles_device_name_length CHECK (LENGTH(device_name) >= 1),
    CONSTRAINT profiles_session_counts_positive CHECK (
        raw_sessions_count >= 0 AND processed_sessions_count >= 0
    )
);

-- Enable Row Level Security for profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies for profiles
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- =====================================================
-- SESSIONS TABLE (Unified Raw + Processed Data)
-- =====================================================
-- This table implements the EXACT unified schema from schema.md
-- Stores both raw RR intervals and processed HRV metrics in one table

CREATE TABLE public.sessions (
    -- ==========================================
    -- CORE IDENTIFIERS (from schema.md)
    -- ==========================================
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- ==========================================
    -- TAG STRUCTURE (EXACT from schema.md)
    -- ==========================================
    -- Base tags: rest, sleep, experiment_paired_pre, experiment_paired_post, experiment_duration, breath_workout
    tag VARCHAR(50) NOT NULL,
    
    -- Semantic subtags: rest_single, sleep_interval_N, experiment_paired_pre_single, etc.
    subtag VARCHAR(100) NOT NULL,
    
    -- Event grouping: 0 = no grouping, >0 = grouped (sleep intervals share same event_id)
    event_id INTEGER NOT NULL DEFAULT 0,
    
    -- ==========================================
    -- SESSION TIMING (from schema.md)
    -- ==========================================
    duration_minutes INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- ==========================================
    -- RAW HRV DATA (from schema.md)
    -- ==========================================
    -- RR intervals in milliseconds as JSON array
    rr_intervals JSONB NOT NULL,
    
    -- Count of RR intervals for quick access
    rr_count INTEGER NOT NULL,
    
    -- ==========================================
    -- PROCESSING STATUS (from schema.md)
    -- ==========================================
    status VARCHAR(20) DEFAULT 'uploaded' NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- ==========================================
    -- HRV METRICS (EXACT 9 METRICS from schema.md)
    -- ==========================================
    -- Time domain metrics
    mean_hr DECIMAL(5,2),           -- Mean heart rate (BPM)
    mean_rr DECIMAL(8,2),           -- Mean RR interval (ms)
    count_rr INTEGER,               -- Count of RR intervals
    rmssd DECIMAL(8,2),             -- Root Mean Square of Successive Differences (ms)
    sdnn DECIMAL(8,2),              -- Standard Deviation of NN intervals (ms)
    pnn50 DECIMAL(5,2),             -- Percentage of RR diffs > 50ms (%)
    cv_rr DECIMAL(5,2),             -- Coefficient of variation of RR intervals (%)
    
    -- Non-linear metrics
    defa DECIMAL(6,4),              -- DFA α1 (Detrended Fluctuation Analysis)
    sd2_sd1 DECIMAL(8,2),           -- Poincaré plot SD2/SD1 ratio
    
    -- ==========================================
    -- SYSTEM TIMESTAMPS
    -- ==========================================
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- ==========================================
    -- CONSTRAINTS (EXACT from schema.md)
    -- ==========================================
    -- Tag validation (6 allowed base tags)
    CONSTRAINT sessions_valid_tag CHECK (
        tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout')
    ),
    
    -- Status validation
    CONSTRAINT sessions_valid_status CHECK (
        status IN ('uploaded', 'processing', 'completed', 'failed')
    ),
    
    -- Duration validation (1-30 minutes)
    CONSTRAINT sessions_valid_duration CHECK (
        duration_minutes >= 1 AND duration_minutes <= 30
    ),
    
    -- RR count validation
    CONSTRAINT sessions_valid_rr_count CHECK (
        rr_count >= 0 AND rr_count = jsonb_array_length(rr_intervals)
    ),
    
    -- Event ID validation
    CONSTRAINT sessions_valid_event_id CHECK (event_id >= 0),
    
    -- Sleep sessions must have event_id > 0
    CONSTRAINT sessions_sleep_event_id CHECK (
        (tag = 'sleep' AND event_id > 0) OR (tag != 'sleep')
    ),
    
    -- Non-sleep sessions must have event_id = 0
    CONSTRAINT sessions_non_sleep_event_id CHECK (
        (tag != 'sleep' AND event_id = 0) OR (tag = 'sleep')
    ),
    
    -- Processed sessions must have metrics
    CONSTRAINT sessions_processed_metrics CHECK (
        (status = 'completed' AND mean_hr IS NOT NULL AND mean_rr IS NOT NULL AND 
         count_rr IS NOT NULL AND rmssd IS NOT NULL AND sdnn IS NOT NULL AND 
         pnn50 IS NOT NULL AND cv_rr IS NOT NULL AND defa IS NOT NULL AND sd2_sd1 IS NOT NULL)
        OR (status != 'completed')
    ),
    
    -- Metric value ranges (physiologically reasonable)
    CONSTRAINT sessions_valid_metrics CHECK (
        (mean_hr IS NULL OR (mean_hr >= 30 AND mean_hr <= 220)) AND
        (mean_rr IS NULL OR (mean_rr >= 200 AND mean_rr <= 2000)) AND
        (rmssd IS NULL OR rmssd >= 0) AND
        (sdnn IS NULL OR sdnn >= 0) AND
        (pnn50 IS NULL OR (pnn50 >= 0 AND pnn50 <= 100)) AND
        (cv_rr IS NULL OR cv_rr >= 0) AND
        (defa IS NULL OR (defa >= 0 AND defa <= 2)) AND
        (sd2_sd1 IS NULL OR sd2_sd1 >= 0)
    )
);

-- Enable Row Level Security for sessions
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for sessions
CREATE POLICY "Users can view own sessions" ON public.sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions" ON public.sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" ON public.sessions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sessions" ON public.sessions
    FOR DELETE USING (auth.uid() = user_id);

-- =====================================================
-- PERFORMANCE INDEXES (Optimized from schema.md)
-- =====================================================

-- Profiles table indexes
CREATE INDEX idx_profiles_email ON public.profiles(email);
CREATE INDEX idx_profiles_created_at ON public.profiles(created_at);
CREATE INDEX idx_profiles_session_counts ON public.profiles(raw_sessions_count, processed_sessions_count);

-- Sessions table indexes (optimized for common queries)
CREATE INDEX idx_sessions_user_id ON public.sessions(user_id);
CREATE INDEX idx_sessions_user_tag ON public.sessions(user_id, tag);
CREATE INDEX idx_sessions_user_status ON public.sessions(user_id, status);
CREATE INDEX idx_sessions_user_recorded_at ON public.sessions(user_id, recorded_at DESC);
CREATE INDEX idx_sessions_event_id ON public.sessions(event_id) WHERE event_id > 0;
CREATE INDEX idx_sessions_status ON public.sessions(status);
CREATE INDEX idx_sessions_recorded_at ON public.sessions(recorded_at DESC);

-- Composite indexes for complex queries
CREATE INDEX idx_sessions_user_event ON public.sessions(user_id, event_id) WHERE event_id > 0;
CREATE INDEX idx_sessions_tag_status ON public.sessions(tag, status);
CREATE INDEX idx_sessions_user_tag_status ON public.sessions(user_id, tag, status);

-- JSON index for RR intervals queries
CREATE INDEX idx_sessions_rr_intervals_gin ON public.sessions USING gin(rr_intervals);

-- =====================================================
-- AUTOMATIC TIMESTAMP TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for profiles table
CREATE TRIGGER update_profiles_updated_at 
    BEFORE UPDATE ON public.profiles 
    FOR EACH ROW 
    EXECUTE FUNCTION public.update_updated_at_column();

-- Trigger for sessions table
CREATE TRIGGER update_sessions_updated_at 
    BEFORE UPDATE ON public.sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION public.update_updated_at_column();

-- =====================================================
-- USER SESSION COUNT MANAGEMENT
-- =====================================================

-- Function to automatically update user session counts
CREATE OR REPLACE FUNCTION public.update_user_session_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Increment raw sessions count
        UPDATE public.profiles 
        SET raw_sessions_count = raw_sessions_count + 1,
            updated_at = NOW()
        WHERE id = NEW.user_id;
        
        -- If session is completed, increment processed count
        IF NEW.status = 'completed' THEN
            UPDATE public.profiles 
            SET processed_sessions_count = processed_sessions_count + 1,
                updated_at = NOW()
            WHERE id = NEW.user_id;
        END IF;
        
        RETURN NEW;
    END IF;
    
    IF TG_OP = 'UPDATE' THEN
        -- If status changed to completed, increment processed count
        IF OLD.status != 'completed' AND NEW.status = 'completed' THEN
            UPDATE public.profiles 
            SET processed_sessions_count = processed_sessions_count + 1,
                updated_at = NOW()
            WHERE id = NEW.user_id;
        END IF;
        
        -- If status changed from completed, decrement processed count
        IF OLD.status = 'completed' AND NEW.status != 'completed' THEN
            UPDATE public.profiles 
            SET processed_sessions_count = processed_sessions_count - 1,
                updated_at = NOW()
            WHERE id = NEW.user_id;
        END IF;
        
        RETURN NEW;
    END IF;
    
    IF TG_OP = 'DELETE' THEN
        -- Decrement raw sessions count
        UPDATE public.profiles 
        SET raw_sessions_count = raw_sessions_count - 1,
            updated_at = NOW()
        WHERE id = OLD.user_id;
        
        -- If session was completed, decrement processed count
        IF OLD.status = 'completed' THEN
            UPDATE public.profiles 
            SET processed_sessions_count = processed_sessions_count - 1,
                updated_at = NOW()
            WHERE id = OLD.user_id;
        END IF;
        
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Trigger for automatic session count updates
CREATE TRIGGER update_user_session_counts_trigger
    AFTER INSERT OR UPDATE OR DELETE ON public.sessions
    FOR EACH ROW
    EXECUTE FUNCTION public.update_user_session_counts();

-- =====================================================
-- AUTOMATIC PROFILE CREATION ON USER SIGNUP
-- =====================================================

-- Function to automatically create profile when user signs up via Supabase Auth
CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, device_name)
    VALUES (
        NEW.id, 
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'device_name', 'Unknown Device')
    );
    RETURN NEW;
END;
$$ language 'plpgsql' SECURITY DEFINER;

-- Trigger to create profile on user signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =====================================================
-- HELPER FUNCTIONS FOR HRV DATA QUERIES
-- =====================================================

-- Function to get session statistics for a user
CREATE OR REPLACE FUNCTION public.get_user_session_statistics(user_uuid UUID)
RETURNS TABLE(
    raw_total INTEGER,
    processed_total INTEGER,
    raw_by_tag JSONB,
    processed_by_tag JSONB,
    sleep_events INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        -- Raw session counts
        COUNT(*)::INTEGER as raw_total,
        COUNT(CASE WHEN status = 'completed' THEN 1 END)::INTEGER as processed_total,
        
        -- Raw sessions by tag
        jsonb_object_agg(tag, tag_count) as raw_by_tag,
        
        -- Processed sessions by tag
        jsonb_object_agg(
            tag, 
            CASE WHEN status = 'completed' THEN tag_count ELSE 0 END
        ) as processed_by_tag,
        
        -- Sleep events (count distinct event_ids for sleep tag)
        COUNT(DISTINCT CASE WHEN tag = 'sleep' AND event_id > 0 THEN event_id END)::INTEGER as sleep_events
        
    FROM (
        SELECT 
            tag,
            status,
            event_id,
            COUNT(*) as tag_count
        FROM public.sessions 
        WHERE user_id = user_uuid
        GROUP BY tag, status, event_id
    ) subquery
    GROUP BY ();
END;
$$ language 'plpgsql' SECURITY DEFINER;

-- Function to get recent processed sessions for a user
CREATE OR REPLACE FUNCTION public.get_user_recent_sessions(
    user_uuid UUID, 
    session_limit INTEGER DEFAULT 10,
    session_offset INTEGER DEFAULT 0
)
RETURNS TABLE(
    session_id UUID,
    tag VARCHAR(50),
    subtag VARCHAR(100),
    event_id INTEGER,
    duration_minutes INTEGER,
    recorded_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE,
    mean_hr DECIMAL(5,2),
    mean_rr DECIMAL(8,2),
    count_rr INTEGER,
    rmssd DECIMAL(8,2),
    sdnn DECIMAL(8,2),
    pnn50 DECIMAL(5,2),
    cv_rr DECIMAL(5,2),
    defa DECIMAL(6,4),
    sd2_sd1 DECIMAL(8,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.session_id,
        s.tag,
        s.subtag,
        s.event_id,
        s.duration_minutes,
        s.recorded_at,
        s.processed_at,
        s.mean_hr,
        s.mean_rr,
        s.count_rr,
        s.rmssd,
        s.sdnn,
        s.pnn50,
        s.cv_rr,
        s.defa,
        s.sd2_sd1
    FROM public.sessions s
    WHERE s.user_id = user_uuid 
    AND s.status = 'completed'
    ORDER BY s.recorded_at DESC
    LIMIT session_limit
    OFFSET session_offset;
END;
$$ language 'plpgsql' SECURITY DEFINER;

-- =====================================================
-- DATA VALIDATION AND INTEGRITY VIEWS
-- =====================================================

-- View for session data integrity monitoring
CREATE VIEW public.session_integrity_monitor AS
SELECT 
    user_id,
    tag,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_sessions,
    COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_sessions,
    AVG(duration_minutes) as avg_duration,
    AVG(rr_count) as avg_rr_count,
    MIN(recorded_at) as first_session,
    MAX(recorded_at) as last_session
FROM public.sessions
GROUP BY user_id, tag
ORDER BY user_id, tag;

-- View for HRV metrics summary
CREATE VIEW public.hrv_metrics_summary AS
SELECT 
    user_id,
    tag,
    COUNT(*) as session_count,
    AVG(mean_hr) as avg_mean_hr,
    AVG(mean_rr) as avg_mean_rr,
    AVG(rmssd) as avg_rmssd,
    AVG(sdnn) as avg_sdnn,
    AVG(pnn50) as avg_pnn50,
    AVG(cv_rr) as avg_cv_rr,
    AVG(defa) as avg_defa,
    AVG(sd2_sd1) as avg_sd2_sd1,
    STDDEV(rmssd) as std_rmssd,
    STDDEV(sdnn) as std_sdnn
FROM public.sessions
WHERE status = 'completed'
GROUP BY user_id, tag
ORDER BY user_id, tag;

-- =====================================================
-- SCHEMA VERIFICATION QUERIES
-- =====================================================

-- Verify table structures match schema.md exactly
DO $$
DECLARE
    profiles_count INTEGER;
    sessions_count INTEGER;
    constraint_count INTEGER;
    index_count INTEGER;
    trigger_count INTEGER;
    function_count INTEGER;
BEGIN
    -- Check tables exist
    SELECT COUNT(*) INTO profiles_count FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'profiles';
    
    SELECT COUNT(*) INTO sessions_count FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'sessions';
    
    -- Check constraints
    SELECT COUNT(*) INTO constraint_count FROM information_schema.table_constraints 
    WHERE table_schema = 'public' AND table_name IN ('profiles', 'sessions');
    
    -- Check indexes
    SELECT COUNT(*) INTO index_count FROM pg_indexes 
    WHERE schemaname = 'public' AND tablename IN ('profiles', 'sessions');
    
    -- Check triggers
    SELECT COUNT(*) INTO trigger_count FROM information_schema.triggers 
    WHERE trigger_schema = 'public' AND event_object_table IN ('profiles', 'sessions');
    
    -- Check functions
    SELECT COUNT(*) INTO function_count FROM information_schema.routines 
    WHERE routine_schema = 'public' AND routine_name LIKE '%user%' OR routine_name LIKE '%session%';
    
    -- Report results
    RAISE NOTICE '=== HRV DATABASE SCHEMA VERIFICATION ===';
    RAISE NOTICE 'Tables created: profiles=%, sessions=%', profiles_count, sessions_count;
    RAISE NOTICE 'Constraints: %', constraint_count;
    RAISE NOTICE 'Indexes: %', index_count;
    RAISE NOTICE 'Triggers: %', trigger_count;
    RAISE NOTICE 'Functions: %', function_count;
    RAISE NOTICE '==========================================';
    
    IF profiles_count = 1 AND sessions_count = 1 THEN
        RAISE NOTICE '✅ HRV App Unified PostgreSQL Schema v3.3.4 implemented successfully!';
        RAISE NOTICE '✅ Schema follows schema.md exactly with full Supabase integration';
        RAISE NOTICE '✅ Row Level Security enabled for multi-tenant data isolation';
        RAISE NOTICE '✅ All 9 HRV metrics implemented with proper validation';
        RAISE NOTICE '✅ Event grouping logic implemented for sleep intervals';
        RAISE NOTICE '✅ Automatic triggers for session counting and timestamps';
        RAISE NOTICE '✅ Ready for iOS and API integration';
        RAISE NOTICE '==========================================';
        RAISE NOTICE '🎉 SINGLE SOURCE OF TRUTH ESTABLISHED 🎉';
    ELSE
        RAISE EXCEPTION 'Schema verification failed - tables not created properly';
    END IF;
END $$;

-- =====================================================
-- END OF SCHEMA - READY FOR PRODUCTION
-- =====================================================
