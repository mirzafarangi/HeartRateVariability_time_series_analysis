#!/usr/bin/env python3
"""
Database Migration: Fix sessions_tag_check constraint
Updates experiment_single -> experiment_duration in database constraint
"""

import os
import psycopg2

def migrate_tag_constraint():
    """Update the sessions_tag_check constraint to use experiment_duration"""
    
    # Direct Supabase connection (bypassing env var issues)
    connection_params = {
        'host': 'aws-0-eu-central-1.pooler.supabase.com',
        'database': 'postgres',
        'user': 'postgres.hmckwsyksbckxfxuzxca',
        'password': 'Slavoj@!64Su',  # From database_config.py default
        'port': 6543
    }
    
    try:
        # Connect to database
        print(f"🔄 Connecting to Supabase: {connection_params['host']}:{connection_params['port']}")
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()
        
        print("🔄 Starting database constraint migration...")
        
        # Drop the old constraint
        print("  Dropping old constraint...")
        cursor.execute("ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_tag_check;")
        
        # Add the new constraint with correct tag
        print("  Adding new constraint with experiment_duration...")
        cursor.execute("""
            ALTER TABLE sessions 
            ADD CONSTRAINT sessions_tag_check 
            CHECK (tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout'));
        """)
        
        # Commit changes
        conn.commit()
        
        print("✅ Migration completed successfully!")
        print("   Updated constraint: experiment_single -> experiment_duration")
        
        # Verify the constraint
        cursor.execute("""
            SELECT conname, pg_get_constraintdef(oid) 
            FROM pg_constraint 
            WHERE conname = 'sessions_tag_check';
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"   Verified constraint: {result[1]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    migrate_tag_constraint()
