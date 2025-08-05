#!/usr/bin/env python3
"""
Simple Database Connection Test
Manually loads environment variables and tests connection to correct Supabase project
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def load_env_file():
    """Manually load environment variables from .env.railway"""
    env_vars = {}
    try:
        with open('.env.railway', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
                    os.environ[key] = value
    except Exception as e:
        print(f"Error loading .env.railway: {e}")
    return env_vars

def test_database_connection():
    """Test database connection with correct project ID"""
    
    print("🔧 Loading environment variables...")
    env_vars = load_env_file()
    
    # Display loaded variables
    host = os.environ.get('SUPABASE_DB_HOST')
    port = os.environ.get('SUPABASE_DB_PORT')
    database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
    user = os.environ.get('SUPABASE_DB_USER', 'postgres')
    
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Database: {database}")
    print(f"   User: {user}")
    
    # Verify we have the correct project ID
    if 'hmckwsyksbckxfxuzxca' in str(host):
        print("✅ Using correct Supabase project: hmckwsyksbckxfxuzxca")
    else:
        print(f"❌ Wrong project ID in host: {host}")
        return False
    
    # Test connection
    print("\n🔗 Testing database connection...")
    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=os.environ.get('SUPABASE_DB_PASSWORD'),
            port=int(port),
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        # Test basic query
        cur.execute("SELECT version()")
        version = cur.fetchone()
        print(f"✅ Connection successful!")
        print(f"   PostgreSQL version: {version['version'][:50]}...")
        
        # Check if hrv_plots table exists
        print("\n📋 Checking hrv_plots table...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'hrv_plots'
        """)
        table_exists = cur.fetchone()
        
        if table_exists:
            print("✅ hrv_plots table exists")
            
            # Count existing plots
            cur.execute("SELECT COUNT(*) as count FROM public.hrv_plots")
            count_result = cur.fetchone()
            print(f"   Existing plots: {count_result['count']}")
            
            # Test functions
            print("\n⚙️ Testing database functions...")
            cur.execute("""
                SELECT routine_name FROM information_schema.routines 
                WHERE routine_schema = 'public' 
                AND routine_name IN ('get_user_hrv_plots', 'upsert_hrv_plot')
            """)
            functions = cur.fetchall()
            
            for func in functions:
                print(f"✅ Function {func['routine_name']} exists")
            
            if len(functions) == 2:
                print("🎉 All database components are ready!")
                return True
            else:
                print(f"❌ Missing functions. Found {len(functions)}/2")
                return False
        else:
            print("❌ hrv_plots table does not exist")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    success = test_database_connection()
    if success:
        print("\n🎉 Database connection test PASSED!")
        print("   Ready to deploy API with fixed database connection.")
    else:
        print("\n❌ Database connection test FAILED!")
        print("   Need to fix database configuration before API deployment.")
