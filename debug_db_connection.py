#!/usr/bin/env python3
"""
Enhanced Database Connection Diagnostic
Debug why the diagnostic script can't find sessions that exist in the iOS app

User ID: 7015839c-4659-4b6c-821c-2906e710a2db
Expected: 31 sessions (8 Rest + 23 Sleep)
"""

import os
import sys
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.railway')

def debug_connection():
    """Debug database connection and authentication"""
    print("🔍 DEBUGGING DATABASE CONNECTION")
    print("=" * 60)
    
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY')
    
    print(f"📊 Environment variables:")
    print(f"   SUPABASE_URL: {url[:50] if url else 'MISSING'}...")
    print(f"   SUPABASE_ANON_KEY: {'SET' if key else 'MISSING'}")
    
    if not url or not key:
        print("❌ ERROR: Missing environment variables")
        return None
    
    try:
        supabase = create_client(url, key)
        print("✅ Supabase client created successfully")
        return supabase
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        return None

def test_basic_queries(supabase: Client):
    """Test basic database queries to identify the issue"""
    print("\n🔍 TESTING BASIC DATABASE QUERIES")
    print("=" * 60)
    
    user_id = "7015839c-4659-4b6c-821c-2906e710a2db"
    
    # Test 1: Check if sessions table exists
    try:
        response = supabase.table('sessions').select('count', count='exact').execute()
        total_count = response.count
        print(f"✅ Sessions table exists with {total_count} total records")
    except Exception as e:
        print(f"❌ Sessions table query failed: {e}")
        return
    
    # Test 2: Check if our user_id exists in ANY format
    try:
        # Try exact match
        response = supabase.table('sessions').select('user_id', count='exact').eq('user_id', user_id).execute()
        exact_count = response.count
        print(f"📊 Exact user_id match: {exact_count} sessions")
        
        # Try case-insensitive match
        response = supabase.table('sessions').select('user_id', count='exact').ilike('user_id', user_id).execute()
        case_count = response.count
        print(f"📊 Case-insensitive match: {case_count} sessions")
        
    except Exception as e:
        print(f"❌ User ID query failed: {e}")
        return
    
    # Test 3: Get sample of all user_ids to see format
    try:
        response = supabase.table('sessions').select('user_id').limit(10).execute()
        if response.data:
            print(f"📊 Sample user_ids in database:")
            for i, session in enumerate(response.data[:5]):
                sample_id = session['user_id']
                print(f"   {i+1}. {sample_id}")
                if sample_id == user_id:
                    print(f"      ✅ EXACT MATCH FOUND!")
        else:
            print("❌ No sessions found in database at all")
    except Exception as e:
        print(f"❌ Sample query failed: {e}")
    
    # Test 4: Check authentication/RLS policies
    try:
        # Try without any filters to see if RLS is blocking
        response = supabase.table('sessions').select('session_id, user_id, tag').limit(5).execute()
        if response.data:
            print(f"✅ Can query sessions without filters: {len(response.data)} records")
        else:
            print("❌ No sessions returned even without filters - RLS issue?")
    except Exception as e:
        print(f"❌ Unfiltered query failed: {e}")

def test_specific_user_query(supabase: Client):
    """Test the exact query used in the diagnostic script"""
    print("\n🔍 TESTING SPECIFIC USER QUERY")
    print("=" * 60)
    
    user_id = "7015839c-4659-4b6c-821c-2906e710a2db"
    
    try:
        # Exact query from diagnostic script
        response = supabase.table('sessions').select(
            'session_id, user_id, recorded_at, tag, subtag, event_id, '
            'duration_minutes, rr_count, mean_hr, mean_rr, '
            'rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1'
        ).eq('user_id', user_id).order('recorded_at').execute()
        
        print(f"📊 Query result: {len(response.data) if response.data else 0} sessions")
        
        if response.data:
            print(f"✅ SUCCESS! Found {len(response.data)} sessions")
            
            # Analyze tags
            df = pd.DataFrame(response.data)
            tag_counts = df['tag'].value_counts()
            print(f"📊 Session breakdown by tag:")
            for tag, count in tag_counts.items():
                print(f"   {tag}: {count} sessions")
                
            return df
        else:
            print("❌ No sessions found with exact diagnostic query")
            return None
            
    except Exception as e:
        print(f"❌ Specific user query failed: {e}")
        print(f"   Error type: {type(e)}")
        print(f"   Error details: {str(e)}")
        return None

def analyze_data_if_found(df):
    """Analyze the data if we successfully retrieve it"""
    if df is None or len(df) == 0:
        return
    
    print("\n🔍 DATA ANALYSIS")
    print("=" * 60)
    
    # Convert recorded_at to datetime
    df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    df = df.sort_values('recorded_at')
    
    # Focus on REST sessions for zig-zag analysis
    rest_df = df[df['tag'] == 'rest']
    
    if len(rest_df) > 0:
        print(f"📊 REST sessions analysis:")
        print(f"   Count: {len(rest_df)}")
        print(f"   Date range: {rest_df['recorded_at'].min()} to {rest_df['recorded_at'].max()}")
        
        # Check for zig-zag pattern
        if len(rest_df) >= 2:
            rmssd_diffs = rest_df['rmssd'].diff()
            direction_changes = (rmssd_diffs * rmssd_diffs.shift(1) < 0).sum()
            print(f"   Direction changes: {direction_changes}")
            print(f"   Zig-zag rate: {direction_changes/len(rest_df)*100:.1f}%")
            
            # Show first few sessions
            print(f"\n📊 First 5 REST sessions (chronological):")
            for i, row in rest_df.head().iterrows():
                print(f"   {row['recorded_at'].strftime('%Y-%m-%d %H:%M')} - RMSSD: {row['rmssd']:.1f}ms")
    else:
        print("❌ No REST sessions found in the data")

def main():
    """Main debugging function"""
    print("🏥 Enhanced Database Connection Diagnostic")
    print("Expected: 31 sessions (8 Rest + 23 Sleep) for user 7015839c-4659-4b6c-821c-2906e710a2db")
    print("=" * 80)
    
    # Step 1: Debug connection
    supabase = debug_connection()
    if not supabase:
        return
    
    # Step 2: Test basic queries
    test_basic_queries(supabase)
    
    # Step 3: Test specific user query
    df = test_specific_user_query(supabase)
    
    # Step 4: Analyze data if found
    analyze_data_if_found(df)
    
    print("\n" + "=" * 80)
    print("🎯 DIAGNOSTIC COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
