#!/usr/bin/env python3
"""
HRV Data Integrity & Chronology Diagnostic Script
Analyzes user REST sessions to identify zig-zag line causes

User ID: 7015839c-4659-4b6c-821c-2906e710a2db
Purpose: Diagnose why clinical-grade chart optimizations aren't fixing zig-zag lines
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import numpy as np
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.railway')

def connect_to_database():
    """Connect to Supabase database"""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_ANON_KEY')
    
    if not url or not key:
        print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_ANON_KEY")
        print("Available env vars:", list(os.environ.keys()))
        sys.exit(1)
    
    print(f"🔗 Connecting to Supabase: {url[:50]}...")
    return create_client(url, key)

def fetch_all_sessions(supabase: Client, user_id: str):
    """Fetch ALL sessions for the user to diagnose what data exists"""
    print(f"📊 Fetching ALL sessions for user: {user_id}")
    
    try:
        # First, get all sessions to see what exists
        response = supabase.table('sessions').select(
            'session_id, user_id, recorded_at, tag, subtag, event_id, '
            'duration_minutes, rr_count, mean_hr, mean_rr, '
            'rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1'
        ).eq('user_id', user_id).order('recorded_at').execute()
        
        if not response.data:
            print(f"❌ NO SESSIONS AT ALL found for user {user_id}")
            print("🔍 This suggests either:")
            print("   1. Wrong user_id format or value")
            print("   2. Sessions were recorded with different user_id")
            print("   3. Database connection issue")
            return None
        
        df = pd.DataFrame(response.data)
        print(f"✅ Found {len(df)} total sessions")
        
        # Analyze tags
        tag_counts = df['tag'].value_counts()
        print(f"📊 Session breakdown by tag:")
        for tag, count in tag_counts.items():
            print(f"   {tag}: {count} sessions")
        
        # Filter for REST sessions
        rest_df = df[df['tag'] == 'rest']
        if len(rest_df) == 0:
            print(f"❌ No REST sessions found (but {len(df)} other sessions exist)")
            print(f"🔍 Available tags: {list(tag_counts.keys())}")
            return None
        
        print(f"✅ Found {len(rest_df)} REST sessions out of {len(df)} total")
        return rest_df
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return None

def analyze_data_integrity(df):
    """Comprehensive data integrity analysis"""
    print("\n" + "="*60)
    print("🔍 DATA INTEGRITY ANALYSIS")
    print("="*60)
    
    # Basic info
    print(f"📊 Total sessions: {len(df)}")
    print(f"📅 Date range: {df['recorded_at'].min()} to {df['recorded_at'].max()}")
    
    # Convert recorded_at to datetime
    df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    df = df.sort_values('recorded_at')
    
    # 1. Check for missing/null RMSSD values
    null_rmssd = df['rmssd'].isnull().sum()
    print(f"🔍 Null RMSSD values: {null_rmssd}")
    
    # 2. Check for duplicate timestamps
    duplicate_times = df['recorded_at'].duplicated().sum()
    print(f"🔍 Duplicate timestamps: {duplicate_times}")
    
    # 3. Check for out-of-order dates (should be 0 after sorting)
    time_diffs = df['recorded_at'].diff()
    negative_diffs = (time_diffs < timedelta(0)).sum()
    print(f"🔍 Out-of-order dates: {negative_diffs}")
    
    # 4. Check for extreme RMSSD values
    rmssd_stats = df['rmssd'].describe()
    print(f"🔍 RMSSD statistics:")
    print(f"   Min: {rmssd_stats['min']:.1f}ms")
    print(f"   Max: {rmssd_stats['max']:.1f}ms")
    print(f"   Mean: {rmssd_stats['mean']:.1f}ms")
    print(f"   Std: {rmssd_stats['std']:.1f}ms")
    
    # 5. Check for extreme jumps between consecutive sessions
    rmssd_diffs = df['rmssd'].diff().abs()
    large_jumps = rmssd_diffs > (rmssd_stats['std'] * 2)
    print(f"🔍 Large RMSSD jumps (>2σ): {large_jumps.sum()}")
    
    # 6. Time gaps between sessions
    time_gaps = time_diffs.dt.total_seconds() / 3600  # Convert to hours
    print(f"🔍 Time gaps between sessions:")
    print(f"   Min gap: {time_gaps.min():.1f} hours")
    print(f"   Max gap: {time_gaps.max():.1f} hours")
    print(f"   Mean gap: {time_gaps.mean():.1f} hours")
    
    return df

def analyze_chronological_issues(df):
    """Analyze potential chronological issues causing zig-zag"""
    print("\n" + "="*60)
    print("📈 CHRONOLOGICAL ZIG-ZAG ANALYSIS")
    print("="*60)
    
    # Calculate rolling average (3-point trailing)
    df['rolling_3'] = df['rmssd'].rolling(window=3, min_periods=1).mean()
    
    # Identify potential zig-zag patterns
    df['rmssd_diff'] = df['rmssd'].diff()
    df['direction_change'] = (df['rmssd_diff'] * df['rmssd_diff'].shift(1)) < 0
    
    direction_changes = df['direction_change'].sum()
    print(f"🔍 Direction changes in RMSSD: {direction_changes}")
    print(f"🔍 Direction change rate: {direction_changes/len(df)*100:.1f}%")
    
    # Check if rolling average smooths the zig-zag
    rolling_changes = (df['rolling_3'].diff() * df['rolling_3'].diff().shift(1) < 0).sum()
    print(f"🔍 Direction changes in rolling average: {rolling_changes}")
    print(f"🔍 Rolling smoothing effectiveness: {(1 - rolling_changes/direction_changes)*100:.1f}%")
    
    return df

def create_diagnostic_plots(df):
    """Create comprehensive diagnostic plots"""
    print("\n📊 Creating diagnostic plots...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('HRV Data Diagnostic Analysis\nUser: 7015839c-4659-4b6c-821c-2906e710a2db', fontsize=16)
    
    # Plot 1: Raw RMSSD over time
    axes[0,0].plot(df['recorded_at'], df['rmssd'], 'o-', color='blue', linewidth=2, markersize=6)
    axes[0,0].set_title('Raw RMSSD Over Time\n(This shows the zig-zag pattern)')
    axes[0,0].set_ylabel('RMSSD (ms)')
    axes[0,0].grid(True, alpha=0.3)
    axes[0,0].tick_params(axis='x', rotation=45)
    
    # Plot 2: RMSSD with rolling average
    axes[0,1].plot(df['recorded_at'], df['rmssd'], 'o-', color='blue', alpha=0.7, label='Raw RMSSD')
    axes[0,1].plot(df['recorded_at'], df['rolling_3'], '--', color='red', linewidth=2, label='3-Point Rolling Avg')
    axes[0,1].set_title('RMSSD with Rolling Average\n(Shows if rolling avg smooths zig-zag)')
    axes[0,1].set_ylabel('RMSSD (ms)')
    axes[0,1].legend()
    axes[0,1].grid(True, alpha=0.3)
    axes[0,1].tick_params(axis='x', rotation=45)
    
    # Plot 3: RMSSD differences (jumps between sessions)
    axes[1,0].bar(range(len(df)-1), df['rmssd_diff'].dropna(), color='orange', alpha=0.7)
    axes[1,0].set_title('RMSSD Jumps Between Sessions\n(Large bars indicate zig-zag causes)')
    axes[1,0].set_xlabel('Session Index')
    axes[1,0].set_ylabel('RMSSD Difference (ms)')
    axes[1,0].grid(True, alpha=0.3)
    
    # Plot 4: Time gaps between sessions
    time_gaps = df['recorded_at'].diff().dt.total_seconds() / 3600
    axes[1,1].bar(range(len(time_gaps)-1), time_gaps.dropna(), color='green', alpha=0.7)
    axes[1,1].set_title('Time Gaps Between Sessions\n(Shows recording consistency)')
    axes[1,1].set_xlabel('Session Index')
    axes[1,1].set_ylabel('Hours Between Sessions')
    axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    plot_filename = f"hrv_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    print(f"📊 Diagnostic plot saved: {plot_filename}")
    
    plt.show()

def generate_recommendations(df):
    """Generate specific recommendations based on analysis"""
    print("\n" + "="*60)
    print("💡 RECOMMENDATIONS")
    print("="*60)
    
    # Check data quality
    null_rmssd = df['rmssd'].isnull().sum()
    duplicate_times = df['recorded_at'].duplicated().sum()
    direction_changes = (df['rmssd'].diff() * df['rmssd'].diff().shift(1) < 0).sum()
    
    if null_rmssd > 0:
        print(f"🔧 FIX: Remove or interpolate {null_rmssd} sessions with null RMSSD values")
    
    if duplicate_times > 0:
        print(f"🔧 FIX: Handle {duplicate_times} sessions with duplicate timestamps")
    
    if direction_changes > len(df) * 0.5:
        print(f"🔧 ISSUE: High zig-zag rate ({direction_changes/len(df)*100:.1f}%)")
        print("   - This is normal for real HRV data, but may look messy in charts")
        print("   - Consider using stronger smoothing (5-point instead of 3-point rolling average)")
        print("   - Consider showing only rolling average line, not raw data points")
    
    # Check if iOS chart sorting is working
    is_sorted = df['recorded_at'].is_monotonic_increasing
    if not is_sorted:
        print("🔧 CRITICAL: Data is not chronologically sorted!")
        print("   - This will definitely cause zig-zag lines in charts")
        print("   - Verify iOS chart sorting logic is being applied")
    else:
        print("✅ Data is properly chronologically sorted")
    
    # Check for statistical layers
    if len(df) >= 3:
        print("✅ Sufficient data for rolling average (≥3 sessions)")
    else:
        print("❌ Insufficient data for rolling average (<3 sessions)")
    
    if len(df) >= 7:
        print("✅ Sufficient data for baseline (≥7 sessions)")
    else:
        print("❌ Insufficient data for baseline (<7 sessions)")
    
    if len(df) >= 30:
        print("✅ Sufficient data for percentiles (≥30 sessions)")
    else:
        print(f"❌ Insufficient data for percentiles ({len(df)}/30 sessions)")

def main():
    """Main diagnostic function"""
    print("🏥 HRV Data Integrity & Chronology Diagnostic")
    print("=" * 60)
    
    user_id = "7015839c-4659-4b6c-821c-2906e710a2db"
    
    # Connect to database
    supabase = connect_to_database()
    
    # Fetch data
    df = fetch_all_sessions(supabase, user_id)
    if df is None:
        return
    
    # Run comprehensive analysis
    df = analyze_data_integrity(df)
    df = analyze_chronological_issues(df)
    
    # Create diagnostic plots
    create_diagnostic_plots(df)
    
    # Generate recommendations
    generate_recommendations(df)
    
    print("\n" + "="*60)
    print("🎯 DIAGNOSTIC COMPLETE")
    print("="*60)
    print("Check the generated plot and recommendations above.")
    print("If data looks clean but charts still zig-zag, the issue is in iOS chart logic.")
    print("If data shows problems, fix the data issues first.")

if __name__ == "__main__":
    main()
