#!/usr/bin/env python3
"""
Database Consistency Investigation Script
Checks date formats and data consistency between DB and API responses
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
import json
from typing import Dict, List, Any

# Load environment variables
from dotenv import load_dotenv
load_dotenv('.env.railway')

def get_db_connection():
    """Get direct database connection"""
    return psycopg2.connect(
        host=os.getenv('DATABASE_HOST'),
        database=os.getenv('DATABASE_NAME'),
        user=os.getenv('DATABASE_USER'),
        password=os.getenv('DATABASE_PASSWORD'),
        port=os.getenv('DATABASE_PORT', 5432)
    )

def investigate_session_dates(user_id: str):
    """Investigate session date formats and types in database"""
    print(f"🔍 INVESTIGATING SESSION DATES FOR USER: {user_id}")
    print("=" * 80)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get all sessions with detailed info
            cursor.execute("""
                SELECT 
                    session_id,
                    tag,
                    subtag,
                    event_id,
                    recorded_at,
                    processed_at,
                    duration_minutes,
                    rmssd,
                    mean_hr,
                    status,
                    EXTRACT(EPOCH FROM recorded_at) as recorded_at_epoch,
                    recorded_at::text as recorded_at_text,
                    DATE(recorded_at) as recorded_at_date_only,
                    TIME(recorded_at) as recorded_at_time_only
                FROM sessions 
                WHERE user_id = %s 
                ORDER BY recorded_at DESC
                LIMIT 10
            """, (user_id,))
            
            sessions = cursor.fetchall()
            
            print(f"📊 FOUND {len(sessions)} SESSIONS")
            print()
            
            for i, session in enumerate(sessions, 1):
                print(f"🔹 SESSION {i}: {session['session_id'][:8]}...")
                print(f"   Tag: {session['tag']}, Event ID: {session['event_id']}")
                print(f"   Status: {session['status']}")
                print(f"   Duration: {session['duration_minutes']} minutes")
                print(f"   RMSSD: {session['rmssd']}")
                print(f"   Mean HR: {session['mean_hr']}")
                print()
                print(f"   📅 DATE ANALYSIS:")
                print(f"   - recorded_at (raw): {session['recorded_at']}")
                print(f"   - recorded_at (type): {type(session['recorded_at'])}")
                print(f"   - recorded_at (text): {session['recorded_at_text']}")
                print(f"   - recorded_at (epoch): {session['recorded_at_epoch']}")
                print(f"   - Date only: {session['recorded_at_date_only']}")
                print(f"   - Time only: {session['recorded_at_time_only']}")
                print(f"   - processed_at: {session['processed_at']}")
                print("-" * 60)
                
    finally:
        conn.close()

def investigate_session_consistency(user_id: str):
    """Compare database data with what API should return"""
    print(f"🔍 INVESTIGATING SESSION CONSISTENCY FOR USER: {user_id}")
    print("=" * 80)
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get sessions for trend analysis comparison
            print("📊 REST SESSIONS (tag='rest', event_id=0):")
            cursor.execute("""
                SELECT session_id, recorded_at, rmssd, tag, event_id
                FROM sessions 
                WHERE user_id = %s AND tag = 'rest' AND event_id = 0
                  AND status = 'completed' AND rmssd IS NOT NULL
                ORDER BY recorded_at
            """, (user_id,))
            
            rest_sessions = cursor.fetchall()
            for session in rest_sessions:
                print(f"  - {session['recorded_at']} | RMSSD: {session['rmssd']}")
            
            print()
            print("📊 SLEEP SESSIONS (tag='sleep', event_id > 0):")
            cursor.execute("""
                SELECT session_id, recorded_at, rmssd, tag, event_id
                FROM sessions 
                WHERE user_id = %s AND tag = 'sleep' AND event_id > 0
                  AND status = 'completed' AND rmssd IS NOT NULL
                ORDER BY event_id DESC, recorded_at
                LIMIT 10
            """, (user_id,))
            
            sleep_sessions = cursor.fetchall()
            for session in sleep_sessions:
                print(f"  - Event {session['event_id']} | {session['recorded_at']} | RMSSD: {session['rmssd']}")
            
            print()
            print("📊 LATEST SLEEP EVENT ANALYSIS:")
            cursor.execute("""
                SELECT MAX(event_id) as latest_event_id
                FROM sessions 
                WHERE user_id = %s AND tag = 'sleep' AND event_id > 0
                  AND status = 'completed'
            """, (user_id,))
            
            result = cursor.fetchone()
            latest_event_id = result['latest_event_id'] if result else None
            
            if latest_event_id:
                print(f"Latest Event ID: {latest_event_id}")
                
                cursor.execute("""
                    SELECT session_id, recorded_at, rmssd
                    FROM sessions 
                    WHERE user_id = %s AND tag = 'sleep' AND event_id = %s
                      AND status = 'completed' AND rmssd IS NOT NULL
                    ORDER BY recorded_at
                """, (user_id, latest_event_id))
                
                latest_intervals = cursor.fetchall()
                print(f"Intervals in latest event: {len(latest_intervals)}")
                for interval in latest_intervals:
                    print(f"  - {interval['recorded_at']} | RMSSD: {interval['rmssd']}")
            
            print()
            print("📊 DATA CONSISTENCY CHECK:")
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(CASE WHEN rmssd IS NULL THEN 1 END) as null_rmssd,
                    COUNT(CASE WHEN recorded_at IS NULL THEN 1 END) as null_recorded_at,
                    COUNT(DISTINCT DATE(recorded_at)) as unique_dates,
                    MIN(recorded_at) as earliest_session,
                    MAX(recorded_at) as latest_session
                FROM sessions 
                WHERE user_id = %s AND status = 'completed'
            """, (user_id,))
            
            stats = cursor.fetchone()
            print(f"Total sessions: {stats['total_sessions']}")
            print(f"Sessions with null RMSSD: {stats['null_rmssd']}")
            print(f"Sessions with null recorded_at: {stats['null_recorded_at']}")
            print(f"Unique dates: {stats['unique_dates']}")
            print(f"Date range: {stats['earliest_session']} to {stats['latest_session']}")
                
    finally:
        conn.close()

if __name__ == "__main__":
    user_id = "7015839c-4659-4b6c-821c-2906e710a2db"
    
    print("🚀 DATABASE CONSISTENCY INVESTIGATION")
    print("=" * 80)
    print()
    
    investigate_session_dates(user_id)
    print()
    investigate_session_consistency(user_id)
    
    print()
    print("✅ INVESTIGATION COMPLETE")
