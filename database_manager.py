#!/usr/bin/env python3
"""
HRV App Database Manager - FINAL CLEAN VERSION
Version: 4.0.0 FINAL
Source: schema.md (Golden Reference) + Supabase Auth Integration

Single script for all database operations:
- Setup unified schema
- Validate connection
- Clean/reset database
"""

import os
import sys
import argparse
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
    """Load environment variables from .env.railway"""
    env_file = Path('.env.railway')
    if not env_file.exists():
        logger.error("❌ .env.railway file not found!")
        return False
    
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                try:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
                except ValueError:
                    continue
    
    logger.info("✅ Environment variables loaded from .env.railway")
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

def validate_connection():
    """Validate database connection and schema"""
    logger.info("🔍 Validating database connection...")
    
    try:
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute('SELECT version();')
        version = cursor.fetchone()
        logger.info(f"✅ Connection successful!")
        logger.info(f"PostgreSQL version: {version['version'][:80]}...")
        
        # Test schema existence
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('profiles', 'sessions')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        logger.info(f"\nSchema validation:")
        expected_tables = ['profiles', 'sessions']
        found_tables = [row['table_name'] for row in tables]
        
        for table in expected_tables:
            if table in found_tables:
                logger.info(f"✅ Table '{table}' exists")
            else:
                logger.info(f"❌ Table '{table}' missing")
        
        cursor.close()
        conn.close()
        
        if len(found_tables) == len(expected_tables):
            logger.info("\n✅ DATABASE VALIDATION: SUCCESSFUL")
            return True
        else:
            logger.info("\n❌ DATABASE VALIDATION: FAILED")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Database validation failed: {e}")
        return False

def setup_schema():
    """Execute the unified database schema"""
    logger.info("📋 Setting up unified database schema...")
    
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
        tag VARCHAR(50) NOT NULL,
        subtag VARCHAR(100) NOT NULL,
        event_id INTEGER NOT NULL DEFAULT 0,
        
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
        logger.error(f"Schema setup failed: {e}")
        conn.rollback()
        conn.close()
        return False

def cleanup_database():
    """Clean/reset database to fresh state"""
    logger.info("🧹 Cleaning database...")
    
    cleanup_sql = """
    -- Clean slate: Drop all tables and recreate
    DROP TABLE IF EXISTS public.sessions CASCADE;
    DROP TABLE IF EXISTS public.profiles CASCADE;
    DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
    """
    
    conn = get_database_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(cleanup_sql)
        conn.commit()
        logger.info("✅ Database cleaned successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        conn.rollback()
        conn.close()
        return False

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='HRV App Database Manager')
    parser.add_argument('action', choices=['setup', 'validate', 'cleanup', 'reset'],
                       help='Action to perform')
    
    args = parser.parse_args()
    
    logger.info(f"🚀 HRV App Database Manager v4.0.0 - Action: {args.action}")
    
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
    
    # Execute action
    if args.action == 'validate':
        success = validate_connection()
    elif args.action == 'setup':
        success = setup_schema()
    elif args.action == 'cleanup':
        success = cleanup_database()
    elif args.action == 'reset':
        logger.info("🔄 Resetting database (cleanup + setup)...")
        success = cleanup_database() and setup_schema()
    
    if success:
        logger.info(f"\n✅ {args.action.upper()} COMPLETED SUCCESSFULLY!")
    else:
        logger.error(f"\n❌ {args.action.upper()} FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
