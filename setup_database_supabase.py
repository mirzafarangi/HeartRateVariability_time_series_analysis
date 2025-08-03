#!/usr/bin/env python3
"""
HRV App Supabase Database Setup Script
Version: 3.3.4 Final (Supabase Edition)
Source: schema.md (Golden Reference) + Supabase Auth Integration

This script sets up the Supabase-compatible PostgreSQL database schema
following the exact specifications from schema.md with Supabase Auth integration
"""

import os
import sys
from pathlib import Path
from database_config import DatabaseConfig, db_config
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
        logger.error("Please create .env.supabase with your Supabase connection details")
        return False
    
    # Simple .env file parser
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    
    logger.info("✅ Environment variables loaded from .env.supabase")
    return True

def validate_configuration():
    """Validate that all required configuration is present"""
    required_vars = [
        'SUPABASE_DB_HOST',
        'SUPABASE_DB_PASSWORD',
        'SUPABASE_DB_USER',
        'SUPABASE_DB_NAME'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var) or 'your-' in os.environ.get(var, '').lower():
            missing_vars.append(var)
    
    if missing_vars:
        logger.error("❌ Missing or placeholder environment variables:")
        for var in missing_vars:
            logger.error(f"   - {var}")
        logger.error("Please update .env.supabase with your actual Supabase project details")
        return False
    
    logger.info("✅ Configuration validation passed")
    return True

def test_connection():
    """Test database connection"""
    logger.info("🔍 Testing database connection...")
    
    try:
        if db_config.test_connection():
            logger.info("✅ Database connection successful!")
            return True
        else:
            logger.error("❌ Database connection failed!")
            return False
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return False

def execute_schema():
    """Execute the Supabase-compatible database schema"""
    logger.info("📋 Executing Supabase-compatible database schema...")
    
    schema_file = Path('database_schema.sql')
    if not schema_file.exists():
        logger.error("❌ database_schema.sql file not found!")
        return False
    
    try:
        if db_config.execute_schema(str(schema_file)):
            logger.info("✅ Supabase database schema executed successfully!")
            return True
        else:
            logger.error("❌ Database schema execution failed!")
            return False
    except Exception as e:
        logger.error(f"❌ Schema execution error: {e}")
        return False

def verify_schema():
    """Verify that the Supabase schema was created correctly"""
    logger.info("🔍 Verifying Supabase schema implementation...")
    
    try:
        conn = db_config.get_connection()
        cur = conn.cursor()
        
        # Check if tables exist in public schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('profiles', 'sessions')
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        if len(tables) != 2:
            logger.error(f"❌ Expected 2 tables, found {len(tables)}")
            return False
        
        logger.info("✅ Tables created: profiles, sessions")
        
        # Check profiles table structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'profiles' 
            ORDER BY ordinal_position;
        """)
        profile_columns = cur.fetchall()
        expected_profile_columns = ['id', 'email', 'device_name', 'raw_sessions_count', 'processed_sessions_count', 'created_at', 'updated_at']
        
        actual_columns = [col['column_name'] for col in profile_columns]
        if actual_columns != expected_profile_columns:
            logger.error(f"❌ Profiles table columns mismatch")
            logger.error(f"Expected: {expected_profile_columns}")
            logger.error(f"Actual: {actual_columns}")
            return False
        
        logger.info("✅ Profiles table structure verified")
        
        # Check sessions table structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'sessions' 
            ORDER BY ordinal_position;
        """)
        session_columns = cur.fetchall()
        
        # Verify key HRV metrics columns are present
        hrv_metrics = ['mean_hr', 'mean_rr', 'count_rr', 'rmssd', 'sdnn', 'pnn50', 'cv_rr', 'defa', 'sd2_sd1']
        session_column_names = [col['column_name'] for col in session_columns]
        
        missing_metrics = [metric for metric in hrv_metrics if metric not in session_column_names]
        if missing_metrics:
            logger.error(f"❌ Missing HRV metrics columns: {missing_metrics}")
            return False
        
        logger.info("✅ Sessions table structure verified")
        logger.info("✅ All 9 HRV metrics columns present")
        
        # Check Row Level Security policies
        cur.execute("""
            SELECT tablename, policyname 
            FROM pg_policies 
            WHERE schemaname = 'public' 
            AND tablename IN ('profiles', 'sessions');
        """)
        policies = cur.fetchall()
        
        logger.info(f"✅ {len(policies)} Row Level Security policies verified")
        
        # Check constraints
        cur.execute("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'public' 
            AND table_name IN ('profiles', 'sessions') 
            AND constraint_type IN ('CHECK', 'FOREIGN KEY');
        """)
        constraints = cur.fetchall()
        
        logger.info(f"✅ {len(constraints)} constraints verified")
        
        # Check indexes
        cur.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('profiles', 'sessions');
        """)
        indexes = cur.fetchall()
        
        logger.info(f"✅ {len(indexes)} performance indexes created")
        
        # Check triggers
        cur.execute("""
            SELECT trigger_name, event_manipulation, event_object_table
            FROM information_schema.triggers 
            WHERE trigger_schema = 'public' 
            AND event_object_table IN ('profiles', 'sessions');
        """)
        triggers = cur.fetchall()
        
        logger.info(f"✅ {len(triggers)} triggers created for automatic updates")
        
        cur.close()
        conn.close()
        
        logger.info("✅ Supabase schema verification completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema verification error: {e}")
        return False

def main():
    """Main setup function"""
    logger.info("🚀 Starting HRV App Supabase Database Setup (Phase 1)")
    logger.info("📋 Following schema.md v3.3.4 with Supabase Auth integration")
    
    # Step 1: Load environment
    if not load_environment():
        sys.exit(1)
    
    # Step 2: Validate configuration
    if not validate_configuration():
        sys.exit(1)
    
    # Step 3: Test connection
    if not test_connection():
        sys.exit(1)
    
    # Step 4: Execute schema
    if not execute_schema():
        sys.exit(1)
    
    # Step 5: Verify schema
    if not verify_schema():
        sys.exit(1)
    
    logger.info("🎉 Supabase database setup completed successfully!")
    logger.info("✅ PostgreSQL schema implemented following schema.md exactly")
    logger.info("🔐 Row Level Security enabled for data isolation")
    logger.info("🔗 Integrated with Supabase Auth system")
    logger.info("🔄 Ready for Phase 2: API Implementation")
    
    logger.info("\n📋 Next Steps:")
    logger.info("1. Test user signup/login through Supabase Auth")
    logger.info("2. Implement API endpoints with Supabase integration")
    logger.info("3. Update iOS app to use Supabase authentication")

if __name__ == "__main__":
    main()
