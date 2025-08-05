#!/usr/bin/env python3
"""
Test single metric with hardcoded vs variable metric to isolate the issue
"""

import requests
import json

def test_hardcoded_metric():
    """Test with hardcoded metric (like debug endpoint)"""
    print("🧪 Testing hardcoded metric (rmssd)...")
    
    url = "https://hrv-brain-api-production.up.railway.app/api/v1/debug/plot-test/7015839c-4659-4b6c-821c-2906e710a2db/rest/rmssd"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: {data.get('success', False)}")
            print(f"Plot data length: {len(data.get('plot_data', ''))}")
            return True
        else:
            print(f"❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def test_variable_metric():
    """Test with variable metric (like batch endpoints)"""
    print("\n🧪 Testing variable metric (mean_hr)...")
    
    url = "https://hrv-brain-api-production.up.railway.app/api/v1/debug/plot-test/7015839c-4659-4b6c-821c-2906e710a2db/rest/mean_hr"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: {data.get('success', False)}")
            print(f"Plot data length: {len(data.get('plot_data', ''))}")
            return True
        else:
            print(f"❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def test_batch_single_metric():
    """Test batch endpoint with single metric"""
    print("\n🧪 Testing batch endpoint single result...")
    
    url = "https://hrv-brain-api-production.up.railway.app/api/v1/plots/refresh-simple/7015839c-4659-4b6c-821c-2906e710a2db/rest"
    
    try:
        response = requests.post(url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('refresh_results', {})
            print(f"mean_hr: {results.get('mean_hr', 'N/A')}")
            print(f"rmssd: {results.get('rmssd', 'N/A')}")
            print(f"Success rate: {data.get('summary', {}).get('success_rate', 0)}")
            return data.get('summary', {}).get('success_rate', 0) > 0
        else:
            print(f"❌ FAILED: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Single Metric Analysis Test")
    print("=" * 50)
    
    # Test hardcoded metric
    hardcoded_works = test_hardcoded_metric()
    
    # Test variable metric
    variable_works = test_variable_metric()
    
    # Test batch processing
    batch_works = test_batch_single_metric()
    
    print("\n📊 ANALYSIS:")
    print(f"Hardcoded rmssd: {'✅ WORKING' if hardcoded_works else '❌ FAILING'}")
    print(f"Variable mean_hr: {'✅ WORKING' if variable_works else '❌ FAILING'}")
    print(f"Batch processing: {'✅ WORKING' if batch_works else '❌ FAILING'}")
    
    if hardcoded_works and variable_works and not batch_works:
        print("\n🔍 CONCLUSION: Individual metrics work, batch processing fails")
        print("   Issue is in batch processing logic, not metric handling")
    elif hardcoded_works and not variable_works:
        print("\n🔍 CONCLUSION: Only hardcoded metrics work")
        print("   Issue is with variable metric handling")
    else:
        print("\n🔍 CONCLUSION: Need more investigation")
