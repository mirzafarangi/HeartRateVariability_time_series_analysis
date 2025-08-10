#!/usr/bin/env python3
"""
Production Database Deep Inspection Script
Analyzes the actual production database structure, constraints, functions, and data patterns
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv('.env.railway')

def get_db_connection():
    """Create a direct PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('SUPABASE_DB_HOST'),
        port=os.getenv('SUPABASE_DB_PORT'),
        database=os.getenv('SUPABASE_DB_NAME'),
        user=os.getenv('SUPABASE_DB_USER'),
        password=os.getenv('SUPABASE_DB_PASSWORD'),
        sslmode='require'
    )

def inspect_table_structure(conn):
    """Inspect the sessions table structure"""
    print("\n" + "="*80)
    print("1. TABLE STRUCTURE ANALYSIS")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get column information
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                generation_expression
            FROM information_schema.columns
            WHERE table_schema = 'public' 
            AND table_name = 'sessions'
            ORDER BY ordinal_position;
        """)
        
        print("\nColumns in sessions table:")
        for col in cur.fetchall():
            print(f"  - {col['column_name']}: {col['data_type']} "
                  f"(nullable: {col['is_nullable']}, "
                  f"default: {col['column_default'] or 'none'}, "
                  f"generated: {col['generation_expression'] or 'no'})")

def inspect_constraints(conn):
    """Inspect all constraints on sessions table"""
    print("\n" + "="*80)
    print("2. CONSTRAINTS ANALYSIS")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get all constraints
        cur.execute("""
            SELECT 
                con.conname AS constraint_name,
                con.contype AS constraint_type,
                pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = 'sessions'
            AND rel.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            ORDER BY con.conname;
        """)
        
        print("\nConstraints on sessions table:")
        for con in cur.fetchall():
            con_type = {
                'c': 'CHECK',
                'f': 'FOREIGN KEY',
                'p': 'PRIMARY KEY',
                'u': 'UNIQUE'
            }.get(con['constraint_type'], con['constraint_type'])
            print(f"\n  {con['constraint_name']} ({con_type}):")
            print(f"    {con['definition']}")

def inspect_indexes(conn):
    """Inspect all indexes on sessions table"""
    print("\n" + "="*80)
    print("3. INDEXES ANALYSIS")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'sessions'
            ORDER BY indexname;
        """)
        
        print("\nIndexes on sessions table:")
        for idx in cur.fetchall():
            print(f"\n  {idx['indexname']}:")
            print(f"    {idx['indexdef']}")

def inspect_triggers(conn):
    """Inspect all triggers on sessions table"""
    print("\n" + "="*80)
    print("4. TRIGGERS ANALYSIS")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                tgname AS trigger_name,
                tgtype,
                proname AS function_name,
                tgisinternal
            FROM pg_trigger t
            JOIN pg_proc p ON t.tgfoid = p.oid
            JOIN pg_class c ON t.tgrelid = c.oid
            WHERE c.relname = 'sessions'
            AND c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND NOT tgisinternal
            ORDER BY tgname;
        """)
        
        triggers = cur.fetchall()
        if triggers:
            print("\nTriggers on sessions table:")
            for trig in triggers:
                print(f"\n  {trig['trigger_name']}:")
                print(f"    Function: {trig['function_name']}")
        else:
            print("\nNo triggers found on sessions table")

def inspect_functions(conn):
    """Inspect all custom functions in the database"""
    print("\n" + "="*80)
    print("5. FUNCTIONS ANALYSIS")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                proname AS function_name,
                pg_get_function_arguments(oid) AS arguments,
                pg_get_function_result(oid) AS return_type
            FROM pg_proc
            WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND proname LIKE 'fn_%'
            ORDER BY proname;
        """)
        
        print("\nCustom functions (fn_* pattern):")
        for func in cur.fetchall():
            print(f"\n  {func['function_name']}({func['arguments']}):")
            print(f"    Returns: {func['return_type']}")

def inspect_data_patterns(conn):
    """Analyze actual data patterns in the database"""
    print("\n" + "="*80)
    print("6. DATA PATTERNS ANALYSIS")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Count sessions by tag
        cur.execute("""
            SELECT tag, COUNT(*) as count
            FROM sessions
            GROUP BY tag
            ORDER BY tag;
        """)
        print("\nSessions by tag:")
        for row in cur.fetchall():
            print(f"  {row['tag']}: {row['count']} sessions")
        
        # Count sessions by tag/subtag combination
        cur.execute("""
            SELECT tag, subtag, COUNT(*) as count
            FROM sessions
            GROUP BY tag, subtag
            ORDER BY tag, subtag;
        """)
        print("\nSessions by tag/subtag combination:")
        for row in cur.fetchall():
            print(f"  {row['tag']}/{row['subtag']}: {row['count']} sessions")
        
        # Check event_id patterns
        cur.execute("""
            SELECT 
                tag,
                MIN(event_id) as min_event_id,
                MAX(event_id) as max_event_id,
                COUNT(DISTINCT event_id) as unique_event_ids
            FROM sessions
            GROUP BY tag
            ORDER BY tag;
        """)
        print("\nEvent ID patterns by tag:")
        for row in cur.fetchall():
            print(f"  {row['tag']}: event_id range [{row['min_event_id']}-{row['max_event_id']}], "
                  f"{row['unique_event_ids']} unique values")
        
        # Check paired mode usage
        cur.execute("""
            SELECT 
                tag,
                subtag,
                COUNT(*) as count,
                COUNT(DISTINCT user_id) as unique_users
            FROM sessions
            WHERE subtag LIKE '%paired%'
            GROUP BY tag, subtag
            ORDER BY tag, subtag;
        """)
        paired_results = cur.fetchall()
        if paired_results:
            print("\nPaired mode usage:")
            for row in paired_results:
                print(f"  {row['tag']}/{row['subtag']}: {row['count']} sessions from {row['unique_users']} users")
        else:
            print("\nNo paired mode sessions found in database")
        
        # Check sleep event grouping
        cur.execute("""
            SELECT 
                event_id,
                COUNT(*) as interval_count,
                MIN(interval_number) as min_interval,
                MAX(interval_number) as max_interval,
                MIN(recorded_at) as first_interval,
                MAX(recorded_at) as last_interval
            FROM sessions
            WHERE tag = 'sleep' AND event_id > 0
            GROUP BY event_id
            ORDER BY event_id DESC
            LIMIT 5;
        """)
        sleep_events = cur.fetchall()
        if sleep_events:
            print("\nRecent sleep events (last 5):")
            for row in sleep_events:
                print(f"  Event {row['event_id']}: {row['interval_count']} intervals "
                      f"(#{row['min_interval']}-#{row['max_interval']}), "
                      f"from {row['first_interval']} to {row['last_interval']}")
        else:
            print("\nNo sleep events found in database")

def inspect_trigger_functions(conn):
    """Get the actual source code of trigger functions"""
    print("\n" + "="*80)
    print("7. TRIGGER FUNCTION SOURCE CODE")
    print("="*80)
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Look for event_id assignment trigger function
        cur.execute("""
            SELECT 
                proname AS function_name,
                prosrc AS source_code
            FROM pg_proc
            WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND (proname LIKE '%event%' OR proname LIKE '%sleep%' OR proname LIKE '%assign%')
            ORDER BY proname;
        """)
        
        functions = cur.fetchall()
        if functions:
            print("\nEvent-related trigger functions:")
            for func in functions:
                print(f"\n  Function: {func['function_name']}")
                print("  Source:")
                for line in func['source_code'].split('\n'):
                    print(f"    {line}")
        else:
            print("\nNo event-related trigger functions found")

def main():
    """Run all inspections"""
    print("\n" + "="*80)
    print("PRODUCTION DATABASE DEEP INSPECTION REPORT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*80)
    
    try:
        conn = get_db_connection()
        print(f"\n✓ Connected to production database")
        
        # Run all inspections
        inspect_table_structure(conn)
        inspect_constraints(conn)
        inspect_indexes(conn)
        inspect_triggers(conn)
        inspect_functions(conn)
        inspect_trigger_functions(conn)
        inspect_data_patterns(conn)
        
        print("\n" + "="*80)
        print("INSPECTION COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
