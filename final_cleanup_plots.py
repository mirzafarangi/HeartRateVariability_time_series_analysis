#!/usr/bin/env python3
"""
Final Database Cleanup - Proper Constraint Handling
Version: 1.0.0
Date: 2025-08-06

This script properly handles constraints and dependencies when dropping plot tables.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

def final_cleanup():
    """Perform final cleanup with proper constraint handling"""
    
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
        print(f"📅 Final cleanup time: {datetime.now()}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    try:
        # Use autocommit to avoid transaction issues
        conn.autocommit = True
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            
            print("\n🎯 FINAL CLEANUP STRATEGY:")
            print("1. Drop table with CASCADE (handles all dependencies)")
            print("2. Drop remaining functions")
            print("3. Verify complete removal")
            print("-" * 50)
            
            # =================================================================
            # 1. DROP HRV_PLOTS TABLE WITH CASCADE (HANDLES ALL DEPENDENCIES)
            # =================================================================
            print("\n📋 DROPPING HRV_PLOTS TABLE WITH CASCADE:")
            print("-" * 50)
            
            try:
                cursor.execute("DROP TABLE IF EXISTS public.hrv_plots CASCADE")
                print("  ✅ Successfully dropped hrv_plots table with CASCADE")
                print("    (This removes table, indexes, constraints, and policies)")
            except Exception as e:
                print(f"  ❌ Error dropping hrv_plots table: {e}")
            
            # =================================================================
            # 2. DROP REMAINING PLOT-RELATED FUNCTIONS
            # =================================================================
            print("\n🔧 DROPPING REMAINING PLOT FUNCTIONS:")
            print("-" * 50)
            
            # Get all functions that contain 'plot' in the name
            cursor.execute("""
                SELECT routine_name FROM information_schema.routines
                WHERE routine_schema = 'public' 
                AND (routine_name LIKE '%plot%' OR routine_name LIKE '%hrv_plots%')
            """)
            
            plot_functions = cursor.fetchall()
            
            if plot_functions:
                for func in plot_functions:
                    try:
                        cursor.execute(f"DROP FUNCTION IF EXISTS public.{func['routine_name']} CASCADE")
                        print(f"  ✅ Dropped function: {func['routine_name']}")
                    except Exception as e:
                        print(f"  ⚠️  Function {func['routine_name']}: {e}")
            else:
                print("  ✅ No plot-related functions found")
            
            # =================================================================
            # 3. DROP ANY OTHER PLOT-RELATED TABLES
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
            # 4. COMPREHENSIVE VERIFICATION
            # =================================================================
            print("\n🔍 COMPREHENSIVE VERIFICATION:")
            print("-" * 50)
            
            # Check ALL tables
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            all_tables = cursor.fetchall()
            
            print("  📋 ALL REMAINING TABLES:")
            for table in all_tables:
                table_name = table['table_name']
                if 'plot' in table_name.lower():
                    print(f"    ❌ {table_name} (PLOT-RELATED - SHOULD BE REMOVED)")
                else:
                    print(f"    ✅ {table_name}")
            
            # Check ALL functions
            cursor.execute("""
                SELECT routine_name FROM information_schema.routines
                WHERE routine_schema = 'public'
                ORDER BY routine_name
            """)
            all_functions = cursor.fetchall()
            
            print("\n  🔧 ALL REMAINING FUNCTIONS:")
            plot_functions_remain = False
            for func in all_functions:
                func_name = func['routine_name']
                if 'plot' in func_name.lower():
                    print(f"    ❌ {func_name} (PLOT-RELATED - SHOULD BE REMOVED)")
                    plot_functions_remain = True
                else:
                    print(f"    ✅ {func_name}")
            
            if not plot_functions_remain:
                print("    ✅ No plot-related functions remain")
            
            # Check ALL indexes
            cursor.execute("""
                SELECT indexname, tablename FROM pg_indexes 
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
            """)
            all_indexes = cursor.fetchall()
            
            print("\n  📇 ALL REMAINING INDEXES:")
            plot_indexes_remain = False
            for idx in all_indexes:
                idx_name = idx['indexname']
                if 'plot' in idx_name.lower():
                    print(f"    ❌ {idx_name} on {idx['tablename']} (PLOT-RELATED - SHOULD BE REMOVED)")
                    plot_indexes_remain = True
                else:
                    print(f"    ✅ {idx_name} on {idx['tablename']}")
            
            if not plot_indexes_remain:
                print("    ✅ No plot-related indexes remain")
            
            # Check ALL policies
            cursor.execute("""
                SELECT policyname, tablename FROM pg_policies 
                WHERE schemaname = 'public'
                ORDER BY tablename, policyname
            """)
            all_policies = cursor.fetchall()
            
            print("\n  🔒 ALL REMAINING RLS POLICIES:")
            plot_policies_remain = False
            for policy in all_policies:
                policy_name = policy['policyname']
                if 'plot' in policy_name.lower():
                    print(f"    ❌ {policy_name} on {policy['tablename']} (PLOT-RELATED - SHOULD BE REMOVED)")
                    plot_policies_remain = True
                else:
                    print(f"    ✅ {policy_name} on {policy['tablename']}")
            
            if not plot_policies_remain:
                print("    ✅ No plot-related policies remain")
            
            # =================================================================
            # 5. FINAL STATUS SUMMARY
            # =================================================================
            print("\n🎯 FINAL CLEANUP SUMMARY:")
            print("-" * 50)
            
            # Check if hrv_plots is completely gone
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'hrv_plots'
                )
            """)
            hrv_plots_exists = cursor.fetchone()['exists']
            
            # Check core tables
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name IN ('profiles', 'sessions')
                ORDER BY table_name
            """)
            core_tables = cursor.fetchall()
            core_intact = len(core_tables) == 2
            
            # Overall status
            cleanup_success = (not hrv_plots_exists and 
                             not plot_functions_remain and 
                             not plot_indexes_remain and 
                             not plot_policies_remain and
                             core_intact)
            
            if cleanup_success:
                print("  🎉 COMPLETE SUCCESS!")
                print("    ✅ hrv_plots table removed")
                print("    ✅ All plot functions removed")
                print("    ✅ All plot indexes removed")
                print("    ✅ All plot policies removed")
                print("    ✅ Core tables (profiles, sessions) intact")
                print("\n🚀 DATABASE IS NOW COMPLETELY CLEAN AND READY!")
            else:
                print("  ⚠️  PARTIAL SUCCESS - Some artifacts may remain:")
                if hrv_plots_exists:
                    print("    ❌ hrv_plots table still exists")
                if plot_functions_remain:
                    print("    ❌ Some plot functions still exist")
                if plot_indexes_remain:
                    print("    ❌ Some plot indexes still exist")
                if plot_policies_remain:
                    print("    ❌ Some plot policies still exist")
                if not core_intact:
                    print("    ❌ Core tables missing or damaged")
            
            print("\n" + "=" * 80)
            print("🏁 Final cleanup completed!")
            
    except Exception as e:
        print(f"❌ Final cleanup error: {e}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🧹 FINAL DATABASE CLEANUP - PROPER CONSTRAINT HANDLING")
    print("This will use CASCADE to properly remove all plot artifacts.")
    
    final_cleanup()
