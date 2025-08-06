#!/usr/bin/env python3
"""
Database State Inspector - Fresh Start Edition
Version: 1.0.0
Date: 2025-08-06

Comprehensive inspection of current database state to verify cleanup
and identify any remaining plot-related tables, functions, or data.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

def inspect_database():
    """Comprehensive database state inspection"""
    
    # Load environment variables
    load_dotenv('.env.railway')
    
    # Database connection
    try:
        conn = psycopg2.connect(
            host=os.getenv('SUPABASE_DB_HOST'),
            database=os.getenv('SUPABASE_DB_NAME'),
            user=os.getenv('SUPABASE_DB_USER'),
            password=os.getenv('SUPABASE_DB_PASSWORD'),
            port=os.getenv('SUPABASE_DB_PORT')
        )
        print(f"✅ Connected to database: {os.getenv('SUPABASE_DB_HOST')}")
        print(f"📅 Inspection time: {datetime.now()}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            
            # =================================================================
            # 1. LIST ALL TABLES IN PUBLIC SCHEMA
            # =================================================================
            print("\n📋 ALL TABLES IN PUBLIC SCHEMA:")
            print("-" * 50)
            
            cursor.execute("""
                SELECT table_name, table_type
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            
            tables = cursor.fetchall()
            for table in tables:
                print(f"  📄 {table['table_name']} ({table['table_type']})")
            
            if not tables:
                print("  ❌ No tables found in public schema")
            
            # =================================================================
            # 2. CHECK SPECIFIC TABLE EXISTENCE
            # =================================================================
            print("\n🔍 SPECIFIC TABLE CHECKS:")
            print("-" * 50)
            
            expected_tables = ['profiles', 'sessions']
            unexpected_tables = ['hrv_plots', 'plot_cache', 'sleep_events']
            
            for table_name in expected_tables + unexpected_tables:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                """, (table_name,))
                
                exists = cursor.fetchone()['exists']
                status = "✅ EXISTS" if exists else "❌ MISSING"
                expected = "EXPECTED" if table_name in expected_tables else "UNEXPECTED"
                print(f"  {status} {table_name} ({expected})")
            
            # =================================================================
            # 3. DETAILED TABLE SCHEMAS
            # =================================================================
            print("\n📊 DETAILED TABLE SCHEMAS:")
            print("-" * 50)
            
            for table in tables:
                table_name = table['table_name']
                print(f"\n  📄 Table: {table_name}")
                
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                
                columns = cursor.fetchall()
                for col in columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    print(f"    - {col['column_name']}: {col['data_type']} {nullable}{default}")
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) as count FROM public.{table_name}")
                count = cursor.fetchone()['count']
                print(f"    📊 Row count: {count}")
            
            # =================================================================
            # 4. LIST ALL FUNCTIONS IN PUBLIC SCHEMA
            # =================================================================
            print("\n🔧 ALL FUNCTIONS IN PUBLIC SCHEMA:")
            print("-" * 50)
            
            cursor.execute("""
                SELECT routine_name, routine_type, data_type
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                ORDER BY routine_name
            """)
            
            functions = cursor.fetchall()
            if functions:
                for func in functions:
                    print(f"  🔧 {func['routine_name']} ({func['routine_type']}) -> {func['data_type']}")
            else:
                print("  ✅ No custom functions found in public schema")
            
            # =================================================================
            # 5. CHECK FOR PLOT-RELATED FUNCTIONS SPECIFICALLY
            # =================================================================
            print("\n🔍 PLOT-RELATED FUNCTION CHECKS:")
            print("-" * 50)
            
            plot_functions = ['get_user_hrv_plots', 'upsert_hrv_plot']
            for func_name in plot_functions:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.routines
                        WHERE routine_schema = 'public' AND routine_name = %s
                    )
                """, (func_name,))
                
                exists = cursor.fetchone()['exists']
                status = "❌ STILL EXISTS" if exists else "✅ REMOVED"
                print(f"  {status} {func_name}")
            
            # =================================================================
            # 6. CHECK TABLE INDEXES
            # =================================================================
            print("\n📇 TABLE INDEXES:")
            print("-" * 50)
            
            cursor.execute("""
                SELECT schemaname, tablename, indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
            """)
            
            indexes = cursor.fetchall()
            current_table = None
            for idx in indexes:
                if idx['tablename'] != current_table:
                    current_table = idx['tablename']
                    print(f"\n  📄 Table: {current_table}")
                print(f"    📇 {idx['indexname']}")
                if 'hrv_plots' in idx['indexname']:
                    print(f"      ⚠️  PLOT-RELATED INDEX STILL EXISTS!")
            
            # =================================================================
            # 7. CHECK ROW LEVEL SECURITY POLICIES
            # =================================================================
            print("\n🔒 ROW LEVEL SECURITY POLICIES:")
            print("-" * 50)
            
            cursor.execute("""
                SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
                FROM pg_policies
                WHERE schemaname = 'public'
                ORDER BY tablename, policyname
            """)
            
            policies = cursor.fetchall()
            current_table = None
            for policy in policies:
                if policy['tablename'] != current_table:
                    current_table = policy['tablename']
                    print(f"\n  📄 Table: {current_table}")
                print(f"    🔒 {policy['policyname']} ({policy['cmd']})")
                if 'plot' in policy['policyname'].lower():
                    print(f"      ⚠️  PLOT-RELATED POLICY STILL EXISTS!")
            
            # =================================================================
            # 8. SAMPLE DATA FROM REMAINING TABLES
            # =================================================================
            print("\n📊 SAMPLE DATA FROM TABLES:")
            print("-" * 50)
            
            for table in tables:
                table_name = table['table_name']
                print(f"\n  📄 Table: {table_name} (first 3 rows)")
                
                try:
                    cursor.execute(f"SELECT * FROM public.{table_name} LIMIT 3")
                    rows = cursor.fetchall()
                    
                    if rows:
                        for i, row in enumerate(rows, 1):
                            print(f"    Row {i}: {dict(row)}")
                    else:
                        print("    (empty table)")
                        
                except Exception as e:
                    print(f"    ❌ Error reading table: {e}")
            
            # =================================================================
            # 9. FINAL CLEANUP VERIFICATION
            # =================================================================
            print("\n🎯 CLEANUP VERIFICATION SUMMARY:")
            print("-" * 50)
            
            # Check if hrv_plots table still exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'hrv_plots'
                )
            """)
            hrv_plots_exists = cursor.fetchone()['exists']
            
            if hrv_plots_exists:
                print("  ❌ CLEANUP INCOMPLETE: hrv_plots table still exists")
                
                # Get details about the hrv_plots table
                cursor.execute("SELECT COUNT(*) as count FROM public.hrv_plots")
                plot_count = cursor.fetchone()['count']
                print(f"     📊 hrv_plots contains {plot_count} records")
                
                if plot_count > 0:
                    cursor.execute("SELECT DISTINCT user_id, tag, metric FROM public.hrv_plots LIMIT 5")
                    sample_plots = cursor.fetchall()
                    print("     📋 Sample plot records:")
                    for plot in sample_plots:
                        print(f"       - User: {plot['user_id']}, Tag: {plot['tag']}, Metric: {plot['metric']}")
            else:
                print("  ✅ CLEANUP SUCCESSFUL: hrv_plots table removed")
            
            # Check expected tables
            expected_exist = all([
                any(t['table_name'] == 'profiles' for t in tables),
                any(t['table_name'] == 'sessions' for t in tables)
            ])
            
            if expected_exist:
                print("  ✅ CORE TABLES: profiles and sessions exist")
            else:
                print("  ❌ CORE TABLES: missing profiles or sessions")
            
            print("\n" + "=" * 80)
            print("🏁 Database inspection completed!")
            
    except Exception as e:
        print(f"❌ Inspection error: {e}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_database()
