#!/usr/bin/env python3
"""
Test script to compare working debug endpoint vs failing sequential endpoint
"""

import requests
import json

def test_working_debug_endpoint():
    """Test the working individual debug endpoint"""
    print("🧪 Testing working debug endpoint...")
    
    url = "https://hrv-brain-api-production.up.railway.app/api/v1/debug/plot-test/7015839c-4659-4b6c-821c-2906e710a2db/rest/mean_hr"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: {data.get('success', False)}")
            print(f"Sessions: {data.get('sessions_count', 0)}")
            print(f"Plot data length: {len(data.get('plot_data', ''))}")
            return True
        else:
            print(f"❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def test_failing_sequential_endpoint():
    """Test the failing sequential endpoint"""
    print("\n🧪 Testing failing sequential endpoint...")
    
    url = "https://hrv-brain-api-production.up.railway.app/api/v1/plots/refresh-sequential/7015839c-4659-4b6c-821c-2906e710a2db/rest"
    
    try:
        response = requests.post(url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success rate: {data.get('summary', {}).get('success_rate', 0)}")
            print(f"Results: {data.get('refresh_results', {})}")
            return data.get('summary', {}).get('success_rate', 0) > 0
        else:
            print(f"❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def test_plot_retrieval():
    """Test plot retrieval to see if any plots exist"""
    print("\n🧪 Testing plot retrieval...")
    
    url = "https://hrv-brain-api-production.up.railway.app/api/v1/plots/user/7015839c-4659-4b6c-821c-2906e710a2db"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total plots: {data.get('total_plots', 0)}")
            print(f"Plots: {list(data.get('plots', {}).keys())}")
            return True
        else:
            print(f"❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    print("🔍 HRV Plot Generation Comparison Test")
    print("=" * 50)
    
    # Test working endpoint
    debug_works = test_working_debug_endpoint()
    
    # Test failing endpoint
    sequential_works = test_failing_sequential_endpoint()
    
    # Test plot retrieval
    retrieval_works = test_plot_retrieval()
    
    print("\n📊 SUMMARY:")
    print(f"Debug endpoint: {'✅ WORKING' if debug_works else '❌ FAILING'}")
    print(f"Sequential endpoint: {'✅ WORKING' if sequential_works else '❌ FAILING'}")
    print(f"Plot retrieval: {'✅ WORKING' if retrieval_works else '❌ FAILING'}")
    
    if debug_works and not sequential_works:
        print("\n🔍 DIAGNOSIS: Individual plot generation works, but sequential batch processing fails")
        print("   This suggests the issue is in the sequential endpoint's loop or database storage logic")
