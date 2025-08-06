#!/usr/bin/env python3
"""
TEMPLATE: Database Reset Script
Reusable template for clearing HRV Brain database

USAGE:
1. Copy this file to reset_database_[purpose].py
2. Modify the reset_options below for your specific needs
3. Run: python3 reset_database_[purpose].py

COMMON USE CASES:
- reset_database_clean.py: Complete clean slate
- reset_database_qa.py: QA testing reset
- reset_database_demo.py: Demo preparation
- reset_database_dev.py: Development reset
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# =====================================================
# CONFIGURATION - MODIFY FOR YOUR SPECIFIC NEEDS
# =====================================================

RESET_OPTIONS = {
    # What to delete
    "delete_sessions": True,      # Delete all session data
    "delete_plots": True,         # Delete all plot data
    "delete_profiles": False,     # Delete user profiles (usually keep)
    
    # Safety options
    "require_confirmation": True,  # Ask user to confirm deletion
    "backup_before_delete": False, # Create backup (not implemented yet)
    "dry_run": False,             # Show what would be deleted without doing it
    
    # Filtering options (if you want selective deletion)
    "filter_by_user": None,       # Delete only specific user's data (UUID)
    "filter_by_tag": None,        # Delete only specific tag data
    "filter_by_date": None,       # Delete data older than date (not implemented)
    
    # Output options
    "verbose": True,              # Show detailed progress
    "show_stats": True,           # Show before/after statistics
}

RESET_PURPOSE = "Template Reset"  # Describe the purpose of this reset

# =====================================================
# CORE FUNCTIONS - DO NOT MODIFY UNLESS NECESSARY
# =====================================================

def load_env_file():
    """Load environment variables from .env.railway"""
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

def get_database_connection():
    """Get database connection with environment variables"""
    load_env_file()
    
    host = os.environ.get('SUPABASE_DB_HOST')
    port = os.environ.get('SUPABASE_DB_PORT')
    database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
    user = os.environ.get('SUPABASE_DB_USER', 'postgres')
    password = os.environ.get('SUPABASE_DB_PASSWORD')
    
    if RESET_OPTIONS["verbose"]:
        print(f"   Host: {host}")
        print(f"   Port: {port}")
        print(f"   Database: {database}")
        print(f"   User: {user}")
    
    # Verify correct project
    if 'hmckwsyksbckxfxuzxca' in str(host):
        if RESET_OPTIONS["verbose"]:
            print("✅ Using correct Supabase project: hmckwsyksbckxfxuzxca")
    else:
        print(f"❌ Wrong project ID in host: {host}")
        return None
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            cursor_factory=RealDictCursor
        )
        if RESET_OPTIONS["verbose"]:
            print("✅ Connection successful!")
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def get_database_stats(cursor):
    """Get current database statistics"""
    stats = {}
    
    # Count sessions
    cursor.execute('SELECT COUNT(*) FROM public.sessions;')
    result = cursor.fetchone()
    stats['sessions'] = result['count'] if result else 0
    
    # Count plots
    cursor.execute('SELECT COUNT(*) FROM public.hrv_plots;')
    result = cursor.fetchone()
    stats['plots'] = result['count'] if result else 0
    
    # Count profiles (if table exists)
    try:
        cursor.execute('SELECT COUNT(*) FROM public.profiles;')
        result = cursor.fetchone()
        stats['profiles'] = result['count'] if result else 0
    except:
        stats['profiles'] = 0
    
    return stats

def build_delete_queries():
    """Build SQL delete queries based on configuration"""
    queries = []
    
    # Build WHERE clauses for filtering
    where_clauses = []
    params = []
    
    if RESET_OPTIONS["filter_by_user"]:
        where_clauses.append("user_id = %s")
        params.append(RESET_OPTIONS["filter_by_user"])
    
    if RESET_OPTIONS["filter_by_tag"]:
        where_clauses.append("tag = %s")
        params.append(RESET_OPTIONS["filter_by_tag"])
    
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Build delete queries
    if RESET_OPTIONS["delete_plots"]:
        queries.append(("plots", f"DELETE FROM public.hrv_plots{where_sql}", params))
    
    if RESET_OPTIONS["delete_sessions"]:
        queries.append(("sessions", f"DELETE FROM public.sessions{where_sql}", params))
    
    if RESET_OPTIONS["delete_profiles"] and not where_clauses:  # Only allow full profile deletion
        queries.append(("profiles", "DELETE FROM public.profiles", []))
    
    return queries

def execute_reset():
    """Execute the database reset based on configuration"""
    
    print(f"🧹 HRV Brain Database Reset - {RESET_PURPOSE}")
    print("=" * 60)
    
    if RESET_OPTIONS["verbose"]:
        print("🔧 Loading environment variables...")
    
    # Get database connection
    conn = get_database_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    # Get initial statistics
    if RESET_OPTIONS["show_stats"]:
        print("\n📊 Current database status:")
        initial_stats = get_database_stats(cursor)
        for table, count in initial_stats.items():
            print(f"   {table.capitalize()}: {count}")
    
    # Build delete queries
    delete_queries = build_delete_queries()
    
    if not delete_queries:
        print("\n✅ No deletion operations configured")
        return True
    
    # Show what will be deleted
    print(f"\n⚠️  This will delete:")
    for table_name, query, params in delete_queries:
        if RESET_OPTIONS["filter_by_user"] or RESET_OPTIONS["filter_by_tag"]:
            print(f"   - {table_name} (filtered)")
        else:
            print(f"   - All {table_name}")
    
    # Dry run mode
    if RESET_OPTIONS["dry_run"]:
        print("\n🧪 DRY RUN MODE - No actual deletion performed")
        for table_name, query, params in delete_queries:
            print(f"   Would execute: {query}")
        return True
    
    # Confirmation
    if RESET_OPTIONS["require_confirmation"]:
        confirm = input("\n🤔 Are you sure you want to proceed? (yes/no): ").lower().strip()
        if confirm not in ['yes', 'y']:
            print("❌ Operation cancelled by user")
            return False
    
    # Execute deletions
    try:
        total_deleted = 0
        for table_name, query, params in delete_queries:
            if RESET_OPTIONS["verbose"]:
                print(f"\n🗑️  Deleting {table_name}...")
            
            cursor.execute(query, params)
            deleted_count = cursor.rowcount
            total_deleted += deleted_count
            
            if RESET_OPTIONS["verbose"]:
                print(f"   Deleted {deleted_count} {table_name}")
        
        # Commit changes
        conn.commit()
        if RESET_OPTIONS["verbose"]:
            print("✅ Changes committed to database")
        
        # Final statistics
        if RESET_OPTIONS["show_stats"]:
            print("\n🔍 Final database status:")
            final_stats = get_database_stats(cursor)
            for table, count in final_stats.items():
                print(f"   {table.capitalize()}: {count}")
        
        print(f"\n🎉 RESET SUCCESSFUL! Deleted {total_deleted} total records")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Reset failed: {e}")
        conn.rollback()
        return False

# =====================================================
# MAIN EXECUTION
# =====================================================

if __name__ == "__main__":
    print(f"HRV Brain Database Reset Template")
    print(f"Purpose: {RESET_PURPOSE}")
    print(f"Configuration: {RESET_OPTIONS}")
    print()
    
    success = execute_reset()
    
    if success:
        print("\n✅ Database reset completed successfully!")
        if RESET_OPTIONS["delete_sessions"]:
            print("\n📱 NEXT STEPS:")
            print("   1. Open iOS HRV Brain app")
            print("   2. Record new sessions")
            print("   3. Check Analysis tab for plot generation")
    else:
        print("\n❌ Database reset failed!")
    
    exit(0 if success else 1)
