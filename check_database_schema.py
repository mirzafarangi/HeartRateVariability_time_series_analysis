#!/usr/bin/env python3
"""
Comprehensive Database Schema Checker for HRV Plots
Analyzes current database state and identifies any issues
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from database_config import DatabaseConfig
import json

def check_database_schema():
    """Comprehensive check of database schema and connectivity"""
    
    results = {
        'connection': {},
        'tables': {},
        'functions': {},
        'permissions': {},
        'test_operations': {}
    }
    
    try:
        # Initialize database configuration
        db_config = DatabaseConfig()
        
        print("🔍 Checking database configuration...")
        print(f"   Host: {db_config.host}")
        print(f"   Database: {db_config.database}")
        print(f"   User: {db_config.user}")
        print(f"   Port: {db_config.port}")
        
        # Test connection
        print("\n🔗 Testing database connection...")
        conn = psycopg2.connect(
            host=db_config.host,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
            port=db_config.port,
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        results['connection'] = {'success': True, 'message': 'Connection successful'}
        print("✅ Database connection successful")
        
        # Check hrv_plots table exists
        print("\n📋 Checking hrv_plots table...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'hrv_plots'
        """)
        table_exists = cur.fetchone()
        
        if table_exists:
            print("✅ hrv_plots table exists")
            results['tables']['hrv_plots_exists'] = True
            
            # Get table schema
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'hrv_plots' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            results['tables']['columns'] = [dict(col) for col in columns]
            
            print(f"   Columns ({len(columns)}):")
            for col in columns:
                print(f"     - {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        else:
            print("❌ hrv_plots table does not exist")
            results['tables']['hrv_plots_exists'] = False
        
        # Check RLS is enabled
        print("\n🔒 Checking Row Level Security...")
        cur.execute("""
            SELECT tablename, rowsecurity FROM pg_tables 
            WHERE schemaname = 'public' AND tablename = 'hrv_plots'
        """)
        rls_info = cur.fetchone()
        if rls_info:
            rls_enabled = rls_info['rowsecurity']
            results['tables']['rls_enabled'] = rls_enabled
            print(f"   RLS enabled: {rls_enabled}")
        
        # Check functions exist
        print("\n⚙️ Checking database functions...")
        cur.execute("""
            SELECT routine_name, routine_type FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_name IN ('get_user_hrv_plots', 'upsert_hrv_plot')
        """)
        functions = cur.fetchall()
        results['functions']['available'] = [dict(func) for func in functions]
        
        for func in functions:
            print(f"✅ Function {func['routine_name']} exists ({func['routine_type']})")
        
        if len(functions) < 2:
            missing_funcs = set(['get_user_hrv_plots', 'upsert_hrv_plot']) - set([f['routine_name'] for f in functions])
            print(f"❌ Missing functions: {missing_funcs}")
        
        # Test upsert function with actual data
        print("\n🧪 Testing upsert function...")
        test_user_id = '7015839c-4659-4b6c-821c-2906e710a2db'
        test_metadata = {'test': True, 'data_points': 5, 'date_range': '2024-01-01 to 2024-01-02'}
        
        try:
            cur.execute("""
                SELECT upsert_hrv_plot(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                test_user_id, 'test_schema_check', 'rmssd', 
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==',  # 1x1 pixel PNG
                json.dumps(test_metadata),
                5, None, None, 50.0, 10.0, 30.0, 70.0, 40.0, 60.0
            ))
            test_plot_id = cur.fetchone()[0]
            conn.commit()
            
            if test_plot_id:
                print(f"✅ Upsert function test successful - plot_id: {test_plot_id}")
                results['test_operations']['upsert'] = {'success': True, 'plot_id': str(test_plot_id)}
                
                # Test retrieval
                cur.execute("""
                    SELECT plot_id, tag, metric, data_points_count, stat_mean 
                    FROM public.hrv_plots 
                    WHERE user_id = %s AND tag = 'test_schema_check'
                """, (test_user_id,))
                retrieved_plot = cur.fetchone()
                
                if retrieved_plot:
                    print(f"✅ Plot retrieval successful - found plot with {retrieved_plot['data_points_count']} data points")
                    results['test_operations']['retrieval'] = {'success': True, 'data': dict(retrieved_plot)}
                else:
                    print("❌ Plot retrieval failed")
                    results['test_operations']['retrieval'] = {'success': False}
                
                # Clean up test data
                cur.execute("DELETE FROM public.hrv_plots WHERE user_id = %s AND tag = 'test_schema_check'", (test_user_id,))
                conn.commit()
                print("🧹 Test data cleaned up")
                
            else:
                print("❌ Upsert function returned NULL")
                results['test_operations']['upsert'] = {'success': False, 'error': 'NULL return'}
                
        except Exception as e:
            print(f"❌ Upsert function test failed: {e}")
            results['test_operations']['upsert'] = {'success': False, 'error': str(e)}
        
        # Check existing plots for the test user
        print(f"\n📊 Checking existing plots for user {test_user_id}...")
        cur.execute("""
            SELECT tag, metric, data_points_count, created_at 
            FROM public.hrv_plots 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (test_user_id,))
        existing_plots = cur.fetchall()
        
        if existing_plots:
            print(f"   Found {len(existing_plots)} existing plots:")
            for plot in existing_plots:
                print(f"     - {plot['tag']}/{plot['metric']}: {plot['data_points_count']} points ({plot['created_at']})")
            results['test_operations']['existing_plots'] = [dict(plot) for plot in existing_plots]
        else:
            print("   No existing plots found")
            results['test_operations']['existing_plots'] = []
        
        print("\n🎉 Database schema check completed successfully!")
        
        # Summary
        print("\n📋 SUMMARY:")
        print(f"   ✅ Connection: Working")
        print(f"   ✅ Table: {'Exists' if results['tables'].get('hrv_plots_exists') else 'Missing'}")
        print(f"   ✅ Functions: {len(results['functions']['available'])}/2 available")
        print(f"   ✅ Upsert Test: {'Passed' if results['test_operations'].get('upsert', {}).get('success') else 'Failed'}")
        print(f"   ✅ Existing Plots: {len(results['test_operations']['existing_plots'])}")
        
        return results
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        results['connection'] = {'success': False, 'error': str(e)}
        return results
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    results = check_database_schema()
    
    # Save results to file for analysis
    with open('database_check_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Results saved to database_check_results.json")
