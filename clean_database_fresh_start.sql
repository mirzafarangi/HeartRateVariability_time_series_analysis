-- FRESH START DATABASE CLEANUP SCRIPT
-- Version: 1.0.0
-- Date: 2025-08-06
-- Purpose: Remove all plot-related tables, functions, and data for clean fresh start
-- 
-- This script will:
-- 1. Drop hrv_plots table and all related functions
-- 2. Keep only profiles and sessions tables (core functionality)
-- 3. Reset database to clean state for new architecture

-- =============================================================================
-- 1. DROP PLOT-RELATED FUNCTIONS
-- =============================================================================

-- Drop plot-related functions
DROP FUNCTION IF EXISTS public.get_user_hrv_plots(UUID);
DROP FUNCTION IF EXISTS public.upsert_hrv_plot(UUID, TEXT, TEXT, JSONB, JSONB, TIMESTAMP WITH TIME ZONE);

-- =============================================================================
-- 2. DROP PLOT-RELATED TABLES
-- =============================================================================

-- Drop hrv_plots table completely
DROP TABLE IF EXISTS public.hrv_plots CASCADE;

-- =============================================================================
-- 3. VERIFY CLEAN STATE
-- =============================================================================

-- Show remaining tables (should only be profiles and sessions)
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Show remaining functions
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_type = 'FUNCTION'
ORDER BY routine_name;

-- =============================================================================
-- 4. CONFIRMATION QUERIES
-- =============================================================================

-- Verify sessions table is intact
SELECT COUNT(*) as session_count FROM public.sessions;

-- Verify profiles table is intact  
SELECT COUNT(*) as profile_count FROM public.profiles;

-- Success message
SELECT 'Database cleanup completed successfully. Only core tables (profiles, sessions) remain.' as status;
