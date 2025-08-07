#!/usr/bin/env python3
"""
RLS-Aware Database Diagnostic
Test both anonymous and service role access to bypass RLS policies

The iOS app likely uses authenticated user context while Python uses anonymous
"""

import os
import sys
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.railway')

def test_anonymous_access():
    """Test with anonymous key (current approach)"""
    print("🔍 TESTING ANONYMOUS ACCESS")
    print("=" * 50)
    
    url = os.getenv('SUPABASE_URL')
    anon_key = os.getenv('SUPABASE_ANON_KEY')
    
    try:
        supabase = create_client(url, anon_key)
        response = supabase.table('sessions').select('*', count='exact').execute()
        print(f"📊 Anonymous access: {response.count} total sessions")
        return response.count > 0
    except Exception as e:
        print(f"❌ Anonymous access failed: {e}")
        return False

def test_service_role_access():
    """Test with service role key (bypasses RLS)"""
    print("\n🔍 TESTING SERVICE ROLE ACCESS (BYPASSES RLS)")
    print("=" * 50)
    
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not service_key:
        print("❌ No service role key found")
        return False
    
    try:
        supabase = create_client(url, service_key)
        response = supabase.table('sessions').select('*', count='exact').execute()
        print(f"📊 Service role access: {response.count} total sessions")
        
        if response.count > 0:
            print("✅ SUCCESS! Sessions found with service role")
            return True
        else:
            print("❌ Still no sessions with service role")
            return False
            
    except Exception as e:
        print(f"❌ Service role access failed: {e}")
        return False

def analyze_sessions_with_service_role():
    """Analyze sessions using service role key"""
    print("\n🔍 ANALYZING SESSIONS WITH SERVICE ROLE")
    print("=" * 50)
    
    url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    user_id = "7015839c-4659-4b6c-821c-2906e710a2db"
    
    try:
        supabase = create_client(url, service_key)
        
        # Get all sessions for our user
        response = supabase.table('sessions').select(
            'session_id, user_id, recorded_at, tag, subtag, '
            'rmssd, sdnn, mean_hr, mean_rr'
        ).eq('user_id', user_id).order('recorded_at').execute()
        
        if not response.data:
            print(f"❌ No sessions found for user {user_id}")
            
            # Check what user_ids actually exist
            all_response = supabase.table('sessions').select('user_id').execute()
            if all_response.data:
                unique_users = set(session['user_id'] for session in all_response.data)
                print(f"📊 Found {len(unique_users)} unique user_ids in database:")
                for i, uid in enumerate(list(unique_users)[:5]):
                    print(f"   {i+1}. {uid}")
                    if uid == user_id:
                        print("      ✅ EXACT MATCH!")
            return None
        
        df = pd.DataFrame(response.data)
        print(f"✅ Found {len(df)} sessions for user")
        
        # Analyze by tag
        tag_counts = df['tag'].value_counts()
        print(f"📊 Sessions by tag:")
        for tag, count in tag_counts.items():
            print(f"   {tag}: {count} sessions")
        
        # Focus on REST sessions for zig-zag analysis
        rest_df = df[df['tag'] == 'rest']
        if len(rest_df) > 0:
            print(f"\n📊 REST sessions analysis:")
            print(f"   Count: {len(rest_df)}")
            
            # Convert to datetime and sort
            rest_df['recorded_at'] = pd.to_datetime(rest_df['recorded_at'])
            rest_df = rest_df.sort_values('recorded_at')
            
            print(f"   Date range: {rest_df['recorded_at'].min()} to {rest_df['recorded_at'].max()}")
            
            # Check for zig-zag pattern
            if len(rest_df) >= 2:
                rmssd_diffs = rest_df['rmssd'].diff()
                direction_changes = (rmssd_diffs * rmssd_diffs.shift(1) < 0).sum()
                print(f"   Direction changes: {direction_changes}")
                print(f"   Zig-zag rate: {direction_changes/len(rest_df)*100:.1f}%")
                
                # Show chronological data
                print(f"\n📊 REST sessions (chronological order):")
                for i, row in rest_df.iterrows():
                    date_str = row['recorded_at'].strftime('%Y-%m-%d %H:%M')
                    print(f"   {date_str} - RMSSD: {row['rmssd']:.1f}ms")
                
                # Check if data is properly sorted
                is_sorted = rest_df['recorded_at'].is_monotonic_increasing
                print(f"\n✅ Data is chronologically sorted: {is_sorted}")
                
                if direction_changes > len(rest_df) * 0.3:
                    print(f"\n🎯 HIGH ZIG-ZAG RATE DETECTED!")
                    print(f"   This is likely normal HRV variability, not a sorting issue")
                    print(f"   Consider using stronger smoothing in charts")
                else:
                    print(f"\n✅ Zig-zag rate is reasonable for HRV data")
        
        return df
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return None

def main():
    """Main diagnostic function"""
    print("🏥 RLS-Aware Database Diagnostic")
    print("Testing both anonymous and service role access")
    print("=" * 80)
    
    # Test anonymous access first
    anon_success = test_anonymous_access()
    
    # Test service role access
    service_success = test_service_role_access()
    
    if service_success:
        # Analyze sessions with service role
        df = analyze_sessions_with_service_role()
        
        if df is not None:
            print(f"\n🎯 CONCLUSION:")
            print(f"   ✅ Sessions exist and are accessible via service role")
            print(f"   ❌ Anonymous access blocked by RLS policies")
            print(f"   🔧 iOS app uses authenticated context, Python needs service role")
    
    print("\n" + "=" * 80)
    print("🎯 RLS DIAGNOSTIC COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
