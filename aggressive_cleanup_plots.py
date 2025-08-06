#!/usr/bin/env python3
"""
Aggressive Database Cleanup - Remove All Plot Artifacts
Version: 1.0.0
Date: 2025-08-06

This script will forcefully remove ALL plot-related database artifacts:
- Drop hrv_plots table with CASCADE
- Remove all plot-related functions
- Remove all plot-related indexes
- Remove all plot-related RLS policies
- Verify complete removal
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

def aggressive_cleanup():
    """Perform aggressive cleanup of all plot-related database artifacts"""
    
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
        print(f"📅 Cleanup time: {datetime.now()}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            
            # =================================================================
            # 1. DROP ALL PLOT-RELATED FUNCTIONS (WITH CASCADE)
            # =================================================================
            print("\n🔧 DROPPING PLOT-RELATED FUNCTIONS:")
            print("-" * 50)
            
            plot_functions = [
                'get_user_hrv_plots',
                'upsert_hrv_plot',
                'refresh_user_plots',
                'delete_user_plots'
            ]
            
            for func_name in plot_functions:
                try:
                    cursor.execute(f"DROP FUNCTION IF EXISTS public.{func_name} CASCADE")
                    print(f"  ✅ Dropped function: {func_name}")
                except Exception as e:
                    print(f"  ⚠️  Function {func_name}: {e}")
            
            # =================================================================
            # 2. DROP ALL PLOT-RELATED POLICIES
            # =================================================================
            print("\n🔒 DROPPING PLOT-RELATED RLS POLICIES:")
            print("-" * 50)
            
            # Get all policies for hrv_plots table
            cursor.execute("""
                SELECT policyname FROM pg_policies 
                WHERE schemaname = 'public' AND tablename = 'hrv_plots'
            """)
            
            policies = cursor.fetchall()
            for policy in policies:
                try:
                    cursor.execute(f"DROP POLICY IF EXISTS \"{policy['policyname']}\" ON public.hrv_plots")
                    print(f"  ✅ Dropped policy: {policy['policyname']}")
                except Exception as e:
                    print(f"  ⚠️  Policy {policy['policyname']}: {e}")
            
            # =================================================================
            # 3. DROP ALL PLOT-RELATED INDEXES
            # =================================================================
            print("\n📇 DROPPING PLOT-RELATED INDEXES:")
            print("-" * 50)
            
            # Get all indexes for hrv_plots table
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE schemaname = 'public' AND tablename = 'hrv_plots'
            """)
            
            indexes = cursor.fetchall()
            for index in indexes:
                try:
                    cursor.execute(f"DROP INDEX IF EXISTS public.{index['indexname']} CASCADE")
                    print(f"  ✅ Dropped index: {index['indexname']}")
                except Exception as e:
                    print(f"  ⚠️  Index {index['indexname']}: {e}")
            
            # =================================================================
            # 4. DROP HRV_PLOTS TABLE WITH CASCADE
            # =================================================================
            print("\n📋 DROPPING HRV_PLOTS TABLE:")
            print("-" * 50)
            
            try:
                cursor.execute("DROP TABLE IF EXISTS public.hrv_plots CASCADE")
                print("  ✅ Dropped table: hrv_plots")
            except Exception as e:
                print(f"  ❌ Error dropping hrv_plots table: {e}")
            
            # =================================================================
            # 5. DROP ANY OTHER PLOT-RELATED TABLES
            # =================================================================
            print("\n📋 DROPPING OTHER PLOT-RELATED TABLES:")
            print("-" * 50)
            
            other_plot_tables = ['plot_cache', 'hrv_plot_data', 'plot_statistics']
            
            for table_name in other_plot_tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS public.{table_name} CASCADE")
                    print(f"  ✅ Dropped table: {table_name}")
                except Exception as e:
                    print(f"  ⚠️  Table {table_name}: {e}")
            
            # =================================================================
            # 6. COMMIT ALL CHANGES
            # =================================================================
            conn.commit()
            print("\n💾 All changes committed to database")
            
            # =================================================================
            # 7. VERIFICATION - CHECK WHAT REMAINS
            # =================================================================
            print("\n🔍 VERIFICATION - CHECKING REMAINING ARTIFACTS:")
            print("-" * 50)
            
            # Check tables
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name LIKE '%plot%'
            """)
            remaining_tables = cursor.fetchall()
            
            if remaining_tables:
                print("  ❌ REMAINING PLOT TABLES:")
                for table in remaining_tables:
                    print(f"    - {table['table_name']}")
            else:
                print("  ✅ No plot-related tables remain")
            
            # Check functions
            cursor.execute("""
                SELECT routine_name FROM information_schema.routines
                WHERE routine_schema = 'public' AND routine_name LIKE '%plot%'
            """)
            remaining_functions = cursor.fetchall()
            
            if remaining_functions:
                print("  ❌ REMAINING PLOT FUNCTIONS:")
                for func in remaining_functions:
                    print(f"    - {func['routine_name']}")
            else:
                print("  ✅ No plot-related functions remain")
            
            # Check indexes
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname LIKE '%plot%'
            """)
            remaining_indexes = cursor.fetchall()
            
            if remaining_indexes:
                print("  ❌ REMAINING PLOT INDEXES:")
                for idx in remaining_indexes:
                    print(f"    - {idx['indexname']}")
            else:
                print("  ✅ No plot-related indexes remain")
            
            # Check policies
            cursor.execute("""
                SELECT policyname FROM pg_policies 
                WHERE schemaname = 'public' AND policyname LIKE '%plot%'
            """)
            remaining_policies = cursor.fetchall()
            
            if remaining_policies:
                print("  ❌ REMAINING PLOT POLICIES:")
                for policy in remaining_policies:
                    print(f"    - {policy['policyname']}")
            else:
                print("  ✅ No plot-related policies remain")
            
            # =================================================================
            # 8. FINAL STATUS CHECK
            # =================================================================
            print("\n🎯 FINAL CLEANUP STATUS:")
            print("-" * 50)
            
            # Verify core tables still exist
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name IN ('profiles', 'sessions')
                ORDER BY table_name
            """)
            core_tables = cursor.fetchall()
            
            expected_core = {'profiles', 'sessions'}
            actual_core = {table['table_name'] for table in core_tables}
            
            if expected_core == actual_core:
                print("  ✅ CORE TABLES INTACT: profiles, sessions")
            else:
                missing = expected_core - actual_core
                extra = actual_core - expected_core
                if missing:
                    print(f"  ❌ MISSING CORE TABLES: {missing}")
                if extra:
                    print(f"  ⚠️  EXTRA CORE TABLES: {extra}")
            
            # Check if hrv_plots is completely gone
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'hrv_plots'
                )
            """)
            hrv_plots_exists = cursor.fetchone()['exists']
            
            if hrv_plots_exists:
                print("  ❌ CLEANUP FAILED: hrv_plots table still exists")
            else:
                print("  ✅ CLEANUP SUCCESS: hrv_plots table completely removed")
            
            print("\n" + "=" * 80)
            print("🏁 Aggressive cleanup completed!")
            
            if not hrv_plots_exists and expected_core == actual_core:
                print("🎉 DATABASE IS NOW CLEAN AND READY FOR FRESH START!")
            else:
                print("⚠️  Some issues remain - manual intervention may be required")
            
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🧹 AGGRESSIVE DATABASE CLEANUP - REMOVE ALL PLOT ARTIFACTS")
    print("This will permanently remove all plot-related database objects.")
    
    # Confirm before proceeding
    response = input("\nProceed with aggressive cleanup? (yes/no): ").lower().strip()
    if response == 'yes':
        aggressive_cleanup()
    else:
        print("❌ Cleanup cancelled by user")
