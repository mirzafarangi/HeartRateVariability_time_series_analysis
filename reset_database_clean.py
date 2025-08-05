#!/usr/bin/env python3
"""
Database Reset Script - Clean Slate
Clears all sessions and plots for a fresh start

Usage: python3 reset_database_clean.py
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

def reset_database():
    """Reset database by clearing all sessions and plots"""
    
    print("🧹 HRV Brain Database Reset - Clean Slate")
    print("=" * 50)
    
    # Load environment variables
    print("🔧 Loading environment variables...")
    env_vars = load_env_file()
    
    # Display connection info
    host = os.environ.get('SUPABASE_DB_HOST')
    port = os.environ.get('SUPABASE_DB_PORT')
    database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
    user = os.environ.get('SUPABASE_DB_USER', 'postgres')
    password = os.environ.get('SUPABASE_DB_PASSWORD')
    
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Database: {database}")
    print(f"   User: {user}")
    
    # Verify correct project
    if 'hmckwsyksbckxfxuzxca' in str(host):
        print("✅ Using correct Supabase project: hmckwsyksbckxfxuzxca")
    else:
        print(f"❌ Wrong project ID in host: {host}")
        return False
    
    try:
        # Connect to database
        print("\n🔗 Connecting to database...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            cursor_factory=RealDictCursor
        )
        print("✅ Connection successful!")
        
        cursor = conn.cursor()
        
        # Check current data before deletion
        print("\n📊 Current database status:")
        
        # Count sessions
        cursor.execute('SELECT COUNT(*) FROM public.sessions;')
        result = cursor.fetchone()
        sessions_count = result['count'] if result else 0
        print(f"   Sessions: {sessions_count}")
        
        # Count plots
        cursor.execute('SELECT COUNT(*) FROM public.hrv_plots;')
        result = cursor.fetchone()
        plots_count = result['count'] if result else 0
        print(f"   Plots: {plots_count}")
        
        if sessions_count == 0 and plots_count == 0:
            print("\n✅ Database is already clean!")
            return True
        
        # Confirm deletion
        print(f"\n⚠️  WARNING: This will delete:")
        print(f"   - {sessions_count} sessions")
        print(f"   - {plots_count} plots")
        
        confirm = input("\n🤔 Are you sure you want to proceed? (yes/no): ").lower().strip()
        if confirm not in ['yes', 'y']:
            print("❌ Operation cancelled by user")
            return False
        
        # Delete all plots first (foreign key dependencies)
        print("\n🗑️  Deleting all plots...")
        cursor.execute('DELETE FROM public.hrv_plots;')
        deleted_plots = cursor.rowcount
        print(f"   Deleted {deleted_plots} plots")
        
        # Delete all sessions
        print("🗑️  Deleting all sessions...")
        cursor.execute('DELETE FROM public.sessions;')
        deleted_sessions = cursor.rowcount
        print(f"   Deleted {deleted_sessions} sessions")
        
        # Commit changes
        conn.commit()
        print("✅ Changes committed to database")
        
        # Verify cleanup
        print("\n🔍 Verifying cleanup...")
        cursor.execute('SELECT COUNT(*) FROM public.sessions;')
        result = cursor.fetchone()
        final_sessions = result['count'] if result else 0
        
        cursor.execute('SELECT COUNT(*) FROM public.hrv_plots;')
        result = cursor.fetchone()
        final_plots = result['count'] if result else 0
        
        print(f"   Final sessions count: {final_sessions}")
        print(f"   Final plots count: {final_plots}")
        
        if final_sessions == 0 and final_plots == 0:
            print("\n🎉 DATABASE RESET SUCCESSFUL!")
            print("   Ready for fresh session recording and plot generation")
        else:
            print("\n❌ Reset incomplete - some data remains")
            return False
        
        cursor.close()
        conn.close()
        
        print("\n📱 NEXT STEPS:")
        print("   1. Open iOS HRV Brain app")
        print("   2. Record 2-3 new sessions")
        print("   3. Check Analysis tab for automatic plot generation")
        print("   4. Verify end-to-end functionality")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    success = reset_database()
    if success:
        print("\n✅ Database reset completed successfully!")
    else:
        print("\n❌ Database reset failed!")
    exit(0 if success else 1)
