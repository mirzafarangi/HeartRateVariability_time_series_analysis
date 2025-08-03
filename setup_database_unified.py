#!/usr/bin/env python3
"""
HRV App Unified Supabase Database Setup Script
Version: 4.0.0 FINAL CLEAN EDITION
Source: schema.md (Golden Reference) + Supabase Auth Integration

CRITICAL FIXES:
- Uses 'profiles' table (NOT 'users' - conflicts with auth.users)
- Proper foreign key references to auth.users(id)
- Unified authentication with service role key
- Clean environment variable handling
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env.supabase"""
    env_file = Path('.env.supabase')
    if not env_file.exists():
        logger.error("❌ .env.supabase file not found!")
        return False
    
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                try:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
                except ValueError:
                    continue
    
    logger.info("✅ Environment variables loaded from .env.supabase")
    return True

def get_database_connection():
    """Get database connection using service role for admin operations"""
    try:
        conn = psycopg2.connect(
            host=os.environ['SUPABASE_DB_HOST'],
            database=os.environ['SUPABASE_DB_NAME'],
            user=os.environ['SUPABASE_DB_USER'],
            password=os.environ['SUPABASE_DB_PASSWORD'],
            port=int(os.environ['SUPABASE_DB_PORT']),
            cursor_factory=RealDictCursor,
            connect_timeout=30
        )
        logger.info("Database connection established successfully")
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def execute_unified_schema():
    """Execute the unified database schema with proper Supabase integration"""
    
    # UNIFIED SCHEMA - FINAL CLEAN VERSION
    schema_sql = """
    -- HRV App Unified Database Schema v4.0.0
    -- CRITICAL: Uses 'profiles' table, NOT 'users' (conflicts with auth.users)
    
    -- Enable UUID extension
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- Drop existing tables if they exist (clean slate)
    DROP TABLE IF EXISTS public.sessions CASCADE;
    DROP TABLE IF EXISTS public.profiles CASCADE;
    
    -- PROFILES TABLE (extends Supabase auth.users)
    -- Note: Supabase provides auth.users table automatically
    CREATE TABLE public.profiles (
        -- Primary key references Supabase auth.users
        id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
        
        -- User information (synced from auth.users)
        email VARCHAR(255) NOT NULL,
        display_name VARCHAR(255),
        
        -- Profile metadata
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Constraints
        CONSTRAINT profiles_email_check CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')
    );
    
    -- SESSIONS TABLE (HRV data storage)
    CREATE TABLE public.sessions (
        -- Core identifiers
        session_id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        
        -- Session metadata (UNIFIED SCHEMA)
        tag VARCHAR(50) NOT NULL,           -- rest, sleep, experiment_paired_pre, etc.
        subtag VARCHAR(100) NOT NULL,       -- rest_single, sleep_interval_1, etc.
        event_id INTEGER NOT NULL DEFAULT 0, -- 0 = standalone, >0 = grouped events
        
        -- Timing
        duration_minutes INTEGER NOT NULL,
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
        
        -- Raw HRV data
        rr_intervals DECIMAL[] NOT NULL,
        rr_count INTEGER NOT NULL,
        
        -- Processing status
        status VARCHAR(20) DEFAULT 'pending',
        processed_at TIMESTAMP WITH TIME ZONE,
        
        -- Sleep-specific fields
        sleep_event_id INTEGER,
        
        -- Processed HRV metrics (JSON for flexibility)
        hrv_metrics JSONB,
        
        -- Timestamps
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Constraints
        CONSTRAINT sessions_tag_check CHECK (tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_single', 'breath_workout')),
        CONSTRAINT sessions_status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
        CONSTRAINT sessions_duration_check CHECK (duration_minutes > 0 AND duration_minutes <= 60),
        CONSTRAINT sessions_rr_count_check CHECK (rr_count > 0 AND rr_count = array_length(rr_intervals, 1))
    );
    
    -- INDEXES for performance
    CREATE INDEX idx_sessions_user_id ON public.sessions(user_id);
    CREATE INDEX idx_sessions_tag ON public.sessions(tag);
    CREATE INDEX idx_sessions_recorded_at ON public.sessions(recorded_at);
    CREATE INDEX idx_sessions_status ON public.sessions(status);
    CREATE INDEX idx_sessions_sleep_event ON public.sessions(sleep_event_id) WHERE sleep_event_id IS NOT NULL;
    
    -- RLS (Row Level Security) policies
    ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
    
    -- Profiles policies
    CREATE POLICY "Users can view own profile" ON public.profiles
        FOR SELECT USING (auth.uid() = id);
    
    CREATE POLICY "Users can update own profile" ON public.profiles
        FOR UPDATE USING (auth.uid() = id);
    
    -- Sessions policies
    CREATE POLICY "Users can view own sessions" ON public.sessions
        FOR SELECT USING (auth.uid() = user_id);
    
    CREATE POLICY "Users can insert own sessions" ON public.sessions
        FOR INSERT WITH CHECK (auth.uid() = user_id);
    
    CREATE POLICY "Users can update own sessions" ON public.sessions
        FOR UPDATE USING (auth.uid() = user_id);
    
    CREATE POLICY "Users can delete own sessions" ON public.sessions
        FOR DELETE USING (auth.uid() = user_id);
    
    -- Function to automatically create profile on user signup
    CREATE OR REPLACE FUNCTION public.handle_new_user()
    RETURNS TRIGGER AS $$
    BEGIN
        INSERT INTO public.profiles (id, email, display_name)
        VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.email));
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    
    -- Trigger to create profile on user signup
    DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
    CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
    
    -- Grant necessary permissions
    GRANT USAGE ON SCHEMA public TO anon, authenticated;
    GRANT ALL ON public.profiles TO anon, authenticated;
    GRANT ALL ON public.sessions TO anon, authenticated;
    """
    
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
        logger.info("✅ Unified database schema executed successfully!")
        
        # Verify tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('profiles', 'sessions')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        logger.info(f"✅ Tables created: {[row['table_name'] for row in tables]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Schema execution failed: {e}")
        conn.rollback()
        conn.close()
        return False

def main():
    """Main setup function"""
    logger.info("🚀 Starting HRV App Unified Database Setup v4.0.0")
    logger.info("📋 Following schema.md with CLEAN Supabase integration")
    
    # Load environment
    if not load_environment():
        sys.exit(1)
    
    # Validate required environment variables
    required_vars = [
        'SUPABASE_DB_HOST', 'SUPABASE_DB_NAME', 'SUPABASE_DB_USER',
        'SUPABASE_DB_PASSWORD', 'SUPABASE_DB_PORT'
    ]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {missing_vars}")
        sys.exit(1)
    
    logger.info("✅ Configuration validation passed")
    
    # Test database connection
    logger.info("🔍 Testing database connection...")
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        version = cursor.fetchone()
        logger.info(f"Database connection test successful: {version}")
        cursor.close()
        conn.close()
        logger.info("✅ Database connection successful!")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)
    
    # Execute schema
    logger.info("📋 Executing unified database schema...")
    if execute_unified_schema():
        logger.info("\n" + "="*60)
        logger.info("✅ HRV APP DATABASE SETUP COMPLETE!")
        logger.info("="*60)
        logger.info("🎯 Schema: UNIFIED & CONSISTENT")
        logger.info("🔐 Auth: Supabase RLS enabled")
        logger.info("📊 Tables: profiles, sessions")
        logger.info("🚀 Ready for API integration!")
        logger.info("="*60)
    else:
        logger.error("❌ Database setup failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
