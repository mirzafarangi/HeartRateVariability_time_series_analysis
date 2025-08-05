#!/usr/bin/env python3
"""
Check Sessions Data in Database
Uses same approach as test_db_connection.py to analyze session upload and plot generation issues
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

def check_sessions_data():
    """Check sessions data and plot generation status"""
    
    print("🔧 Loading environment variables...")
    env_vars = load_env_file()
    
    # Display loaded variables
    host = os.environ.get('SUPABASE_DB_HOST')
    port = os.environ.get('SUPABASE_DB_PORT')
    database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
    user = os.environ.get('SUPABASE_DB_USER', 'postgres')
    password = os.environ.get('SUPABASE_DB_PASSWORD')
    
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
    
    try:
        # Test connection
        print("\n🔗 Testing database connection...")
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
        
        # Check total sessions
        print("\n📊 Checking sessions data...")
        cursor.execute('SELECT COUNT(*) FROM public.sessions;')
        result = cursor.fetchone()
        total_sessions = result['count'] if result else 0
        print(f"   Total sessions in database: {total_sessions}")
        
        if total_sessions > 0:
            # Check recent sessions
            cursor.execute("""
                SELECT user_id, tag, subtag, event_id, recorded_at, status, 
                       CASE WHEN rmssd IS NOT NULL THEN 'processed' ELSE 'raw_only' END as data_type
                FROM public.sessions 
                ORDER BY recorded_at DESC 
                LIMIT 5;
            """)
            recent_sessions = cursor.fetchall()
            print(f"   Recent sessions ({len(recent_sessions)} found):")
            for i, session in enumerate(recent_sessions, 1):
                user_id, tag, subtag, event_id, recorded_at, status, data_type = session
                print(f"     {i}. User: {user_id[:8]}..., Tag: {tag}, Status: {status}, Type: {data_type}")
                print(f"        Date: {recorded_at}")
            
            # Check unique users
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM public.sessions;')
            unique_users = cursor.fetchone()[0]
            print(f"   Unique users: {unique_users}")
            
            # Check tags distribution
            cursor.execute("""
                SELECT tag, COUNT(*) as count 
                FROM public.sessions 
                GROUP BY tag 
                ORDER BY count DESC;
            """)
            tag_counts = cursor.fetchall()
            print(f"   Tag distribution:")
            for tag, count in tag_counts:
                print(f"     - {tag}: {count} sessions")
            
            # Get a sample user_id for testing
            cursor.execute('SELECT DISTINCT user_id FROM public.sessions LIMIT 1;')
            sample_user = cursor.fetchone()
            if sample_user:
                sample_user_id = sample_user[0]
                print(f"\n🧪 Sample user for testing: {sample_user_id[:8]}...")
                
                # Check this user's sessions by tag
                cursor.execute("""
                    SELECT tag, COUNT(*) as count 
                    FROM public.sessions 
                    WHERE user_id = %s
                    GROUP BY tag;
                """, (sample_user_id,))
                user_tags = cursor.fetchall()
                print(f"   This user's sessions by tag:")
                for tag, count in user_tags:
                    print(f"     - {tag}: {count} sessions")
        
        # Check hrv_plots table
        print("\n📈 Checking hrv_plots table...")
        cursor.execute('SELECT COUNT(*) FROM public.hrv_plots;')
        total_plots = cursor.fetchone()[0]
        print(f"   Total plots in database: {total_plots}")
        
        if total_plots > 0:
            cursor.execute("""
                SELECT user_id, tag, metric, created_at, LENGTH(plot_data) as data_size
                FROM public.hrv_plots 
                ORDER BY created_at DESC 
                LIMIT 5;
            """)
            recent_plots = cursor.fetchall()
            print(f"   Recent plots ({len(recent_plots)} found):")
            for i, plot in enumerate(recent_plots, 1):
                user_id, tag, metric, created_at, data_size = plot
                print(f"     {i}. User: {user_id[:8]}..., Tag: {tag}, Metric: {metric}")
                print(f"        Size: {data_size} bytes, Created: {created_at}")
        else:
            print("   ❌ NO PLOTS FOUND - This confirms the root cause!")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎯 ANALYSIS COMPLETE")
        if total_sessions > 0 and total_plots == 0:
            print("   🚨 CRITICAL ISSUE: Sessions exist but NO plots generated!")
            print("   📋 Root cause: Plot generation failing during session upload")
        elif total_sessions == 0:
            print("   🚨 CRITICAL ISSUE: NO sessions found in database!")
            print("   📋 Root cause: Session upload from iOS app failing")
        else:
            print("   ✅ Both sessions and plots found - system working")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_sessions_data()
