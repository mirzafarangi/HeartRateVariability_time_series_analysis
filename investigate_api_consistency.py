#!/usr/bin/env python3
"""
API Consistency Investigation Script
Compares API responses with expected data formats and identifies inconsistencies
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any

BASE_URL = "https://hrv-brain-api-production.up.railway.app"
USER_ID = "7015839c-4659-4b6c-821c-2906e710a2db"

def investigate_processed_sessions():
    """Investigate processed sessions API response"""
    print("🔍 INVESTIGATING PROCESSED SESSIONS API")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/v1/sessions/processed/{USER_ID}"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            sessions = data.get('sessions', [])
            
            print(f"📊 FOUND {len(sessions)} PROCESSED SESSIONS")
            print(f"Total Count: {data.get('total_count', 'N/A')}")
            print()
            
            for i, session in enumerate(sessions[:5], 1):  # Show first 5
                print(f"🔹 SESSION {i}:")
                print(f"   Session ID: {session.get('session_id', 'N/A')}")
                print(f"   Tag: {session.get('tag', 'N/A')}")
                print(f"   Subtag: {session.get('subtag', 'N/A')}")
                print(f"   Event ID: {session.get('event_id', 'N/A')}")
                print(f"   Status: {session.get('status', 'N/A')}")
                print(f"   Duration: {session.get('duration_minutes', 'N/A')} minutes")
                
                # Date analysis
                recorded_at = session.get('recorded_at', 'N/A')
                processed_at = session.get('processed_at', 'N/A')
                print(f"   📅 DATES:")
                print(f"   - Recorded At: {recorded_at}")
                print(f"   - Processed At: {processed_at}")
                
                # Try to parse dates
                if recorded_at != 'N/A':
                    try:
                        parsed_date = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
                        print(f"   - Parsed Date: {parsed_date}")
                        print(f"   - Date Only: {parsed_date.date()}")
                        print(f"   - Time Only: {parsed_date.time()}")
                    except Exception as e:
                        print(f"   - Date Parse Error: {e}")
                
                # HRV metrics
                hrv_metrics = session.get('hrv_metrics', {})
                if hrv_metrics:
                    print(f"   💓 HRV METRICS:")
                    for metric, value in hrv_metrics.items():
                        print(f"   - {metric}: {value}")
                
                print("-" * 40)
                
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def investigate_trend_endpoints():
    """Investigate all trend endpoints for date consistency"""
    print("🔍 INVESTIGATING TREND ENDPOINTS")
    print("=" * 60)
    
    endpoints = [
        ("Rest Trend", f"{BASE_URL}/api/v1/trends/rest?user_id={USER_ID}"),
        ("Sleep Interval", f"{BASE_URL}/api/v1/trends/sleep-interval?user_id={USER_ID}"),
        ("Sleep Event", f"{BASE_URL}/api/v1/trends/sleep-event?user_id={USER_ID}"),
        ("Test Sleep Interval", f"{BASE_URL}/api/v1/test/sleep-interval?user_id={USER_ID}")
    ]
    
    for name, url in endpoints:
        print(f"📊 {name.upper()}:")
        
        try:
            response = requests.get(url, timeout=30)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Analyze raw data
                raw_data = data.get('raw', [])
                print(f"   Raw Data Points: {len(raw_data)}")
                
                if raw_data:
                    print(f"   📅 DATE ANALYSIS:")
                    
                    # Check date formats
                    date_formats = set()
                    unique_dates = set()
                    
                    for point in raw_data[:3]:  # Check first 3 points
                        if 'date' in point:
                            date_val = point['date']
                            date_formats.add(type(date_val).__name__)
                            unique_dates.add(date_val)
                            print(f"   - Date: {date_val} (type: {type(date_val).__name__})")
                        elif 'timestamp' in point:
                            timestamp_val = point['timestamp']
                            date_formats.add(f"timestamp_{type(timestamp_val).__name__}")
                            unique_dates.add(timestamp_val)
                            print(f"   - Timestamp: {timestamp_val} (type: {type(timestamp_val).__name__})")
                        
                        rmssd = point.get('rmssd', 'N/A')
                        print(f"   - RMSSD: {rmssd}")
                    
                    print(f"   Date Formats Found: {list(date_formats)}")
                    print(f"   Unique Dates: {len(unique_dates)}")
                    print(f"   All Same Date?: {len(unique_dates) == 1}")
                    
                    if len(unique_dates) == 1:
                        print(f"   ⚠️  WARNING: All points have same date: {list(unique_dates)[0]}")
                
                # Check other fields
                other_fields = ['rolling_avg', 'baseline', 'sd_band', 'percentile_10', 'percentile_90', 'message']
                for field in other_fields:
                    if field in data:
                        value = data[field]
                        if field == 'rolling_avg' and isinstance(value, list):
                            print(f"   {field}: {len(value)} points")
                        else:
                            print(f"   {field}: {value}")
                
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
        
        print("-" * 40)

def investigate_data_consistency():
    """Compare data consistency across different endpoints"""
    print("🔍 INVESTIGATING DATA CONSISTENCY")
    print("=" * 60)
    
    # Get processed sessions
    processed_url = f"{BASE_URL}/api/v1/sessions/processed/{USER_ID}"
    
    try:
        response = requests.get(processed_url, timeout=30)
        if response.status_code == 200:
            processed_data = response.json()
            sessions = processed_data.get('sessions', [])
            
            # Analyze by tag
            rest_sessions = [s for s in sessions if s.get('tag') == 'rest']
            sleep_sessions = [s for s in sessions if s.get('tag') == 'sleep']
            
            print(f"📊 PROCESSED SESSIONS BREAKDOWN:")
            print(f"   Total Sessions: {len(sessions)}")
            print(f"   Rest Sessions: {len(rest_sessions)}")
            print(f"   Sleep Sessions: {len(sleep_sessions)}")
            
            # Check date consistency in processed sessions
            if rest_sessions:
                print(f"   📅 REST SESSION DATES:")
                for session in rest_sessions[:3]:
                    recorded_at = session.get('recorded_at', 'N/A')
                    rmssd = session.get('hrv_metrics', {}).get('rmssd', 'N/A')
                    print(f"   - {recorded_at} | RMSSD: {rmssd}")
            
            if sleep_sessions:
                print(f"   📅 SLEEP SESSION DATES:")
                for session in sleep_sessions[:5]:
                    recorded_at = session.get('recorded_at', 'N/A')
                    event_id = session.get('event_id', 'N/A')
                    rmssd = session.get('hrv_metrics', {}).get('rmssd', 'N/A')
                    print(f"   - Event {event_id} | {recorded_at} | RMSSD: {rmssd}")
            
            print()
            print("🔍 COMPARING WITH TREND ENDPOINTS:")
            
            # Compare with rest trend
            rest_trend_url = f"{BASE_URL}/api/v1/trends/rest?user_id={USER_ID}"
            rest_response = requests.get(rest_trend_url, timeout=30)
            
            if rest_response.status_code == 200:
                rest_trend = rest_response.json()
                trend_points = rest_trend.get('raw', [])
                
                print(f"   Rest Trend Points: {len(trend_points)}")
                print(f"   Processed Rest Sessions: {len(rest_sessions)}")
                print(f"   Count Match: {len(trend_points) == len(rest_sessions)}")
                
                if trend_points:
                    print(f"   First Trend Point Date: {trend_points[0].get('date', 'N/A')}")
                    if rest_sessions:
                        first_session_date = rest_sessions[0].get('recorded_at', 'N/A')
                        print(f"   First Session Date: {first_session_date}")
                        
                        # Try to compare dates
                        try:
                            trend_date = trend_points[0].get('date', '')
                            session_datetime = datetime.fromisoformat(first_session_date.replace('Z', '+00:00'))
                            session_date = session_datetime.date().isoformat()
                            
                            print(f"   Date Comparison: {trend_date} vs {session_date}")
                            print(f"   Dates Match: {trend_date == session_date}")
                        except Exception as e:
                            print(f"   Date Comparison Error: {e}")
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    print("🚀 API CONSISTENCY INVESTIGATION")
    print("=" * 80)
    print()
    
    investigate_processed_sessions()
    print()
    investigate_trend_endpoints()
    print()
    investigate_data_consistency()
    
    print()
    print("✅ INVESTIGATION COMPLETE")
