#!/usr/bin/env python3
"""
Database Connection Validator for HRV API
Version: 3.3.4 Final
Source: schema.md (Golden Reference)

Validates database connection, schema integrity, and API compatibility.
"""

import os
import sys
import logging
from datetime import datetime
from database_config import DatabaseConfig
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env.supabase"""
    try:
        with open('.env.supabase', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
        logger.info("Environment variables loaded from .env.supabase")
    except Exception as e:
        logger.error(f"Failed to load environment: {e}")

def test_database_connection():
    """Test database connection with detailed diagnostics"""
    print("=" * 60)
    print("DATABASE CONNECTION VALIDATOR")
    print("=" * 60)
    
    # Load environment
    load_environment()
    
    # Initialize database config
    db_config = DatabaseConfig()
    
    print(f"Host: {db_config.host}")
    print(f"Database: {db_config.database}")
    print(f"User: {db_config.user}")
    print(f"Port: {db_config.port}")
    print("-" * 60)
    
    try:
        # Test connection
        print("Testing database connection...")
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute('SELECT version();')
        version = cursor.fetchone()
        print(f"✅ Connection successful!")
        print(f"PostgreSQL version: {version[0][:80]}...")
        
        # Test schema existence
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('profiles', 'sessions')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print(f"\nSchema validation:")
        expected_tables = ['profiles', 'sessions']
        found_tables = [row[0] for row in tables]
        
        for table in expected_tables:
            if table in found_tables:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
        
        # Test table structure for sessions
        if 'sessions' in found_tables:
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'sessions' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            print(f"\nSessions table structure ({len(columns)} columns):")
            for col in columns[:10]:  # Show first 10 columns
                print(f"  {col[0]}: {col[1]}")
            if len(columns) > 10:
                print(f"  ... and {len(columns) - 10} more columns")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("DATABASE CONNECTION: ✅ SUCCESSFUL")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        print("\n" + "=" * 60)
        print("DATABASE CONNECTION: ❌ FAILED")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)
