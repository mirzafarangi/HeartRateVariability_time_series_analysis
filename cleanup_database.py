#!/usr/bin/env python3
"""
Database Cleanup Script for HRV App
Removes existing tables to allow clean Supabase schema installation
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
        return False
    
    # Simple .env file parser
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    
    logger.info("✅ Environment variables loaded")
    return True

def cleanup_database():
    """Remove existing tables and functions"""
    logger.info("🧹 Cleaning up existing database objects...")
    
    try:
        conn = db_config.get_connection()
        cur = conn.cursor()
        
        # Drop tables in correct order (sessions first due to foreign key)
        cleanup_commands = [
            "DROP TRIGGER IF EXISTS update_user_session_counts_trigger ON public.sessions;",
            "DROP TRIGGER IF EXISTS update_sessions_updated_at ON public.sessions;",
            "DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;",
            "DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;",
            "DROP FUNCTION IF EXISTS public.update_user_session_counts();",
            "DROP FUNCTION IF EXISTS public.update_updated_at_column();",
            "DROP FUNCTION IF EXISTS public.handle_new_user();",
            "DROP TABLE IF EXISTS public.sessions CASCADE;",
            "DROP TABLE IF EXISTS public.profiles CASCADE;",
            "DROP TABLE IF EXISTS public.users CASCADE;"
        ]
        
        # Execute each command individually to handle missing objects gracefully
        for command in cleanup_commands:
            try:
                cur.execute(command)
                conn.commit()
                logger.info(f"✅ Executed: {command[:50]}...")
            except Exception as e:
                logger.warning(f"⚠️  Skipped: {command[:50]}... ({e})")
                conn.rollback()
        
        logger.info("✅ Database cleanup completed successfully!")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database cleanup error: {e}")
        return False

def main():
    """Main cleanup function"""
    logger.info("🧹 Starting Database Cleanup")
    
    # Load environment
    if not load_environment():
        sys.exit(1)
    
    # Test connection
    try:
        if not db_config.test_connection():
            logger.error("❌ Database connection failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        sys.exit(1)
    
    # Cleanup database
    if not cleanup_database():
        sys.exit(1)
    
    logger.info("🎉 Database cleanup completed!")
    logger.info("✅ Ready to execute clean Supabase schema")

if __name__ == "__main__":
    main()
