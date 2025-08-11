#!/usr/bin/env python3
"""
Test script to verify the baseline endpoint returns the exact structure specified.
Tests all fields, nested objects, and data types.
"""

import requests
import json
import sys
from typing import Dict, List, Any, Optional

# Test configuration
API_URL = "http://localhost:5001/api/v1/analytics/baseline"
TEST_USER_ID = "7015839c-4659-4b6c-821c-2906e710a2db"

# Expected structure definition
EXPECTED_STRUCTURE = {
    "top_level": {
        "status": str,
        "api_version": str,
        "user_id": str,
        "tag": str,
        "metrics": list,
        "m_points_requested": int,
        "m_points_actual": int,
        "n_points_requested": int,
        "n_points_actual": int,
        "total_sessions": int,
        "max_sessions_applied": (int, type(None)),
        "updated_at": str,
        "fixed_baseline": dict,
        "dynamic_baseline": list,
        "warnings": list,
        "notes": dict
    },
    "fixed_baseline_metric": {
        "count": int,
        "mean": (float, type(None)),
        "sd": (float, type(None)),
        "median": (float, type(None)),
        "sd_median": (float, type(None)),
        "mean_minus_1sd": (float, type(None)),
        "mean_plus_1sd": (float, type(None)),
        "mean_minus_2sd": (float, type(None)),
        "mean_plus_2sd": (float, type(None)),
        "median_minus_1sd": (float, type(None)),
        "median_plus_1sd": (float, type(None)),
        "median_minus_2sd": (float, type(None)),
        "median_plus_2sd": (float, type(None)),
        "min": (float, type(None)),
        "max": (float, type(None)),
        "range": (float, type(None))
    },
    "dynamic_session": {
        "session_id": str,
        "timestamp": str,
        "duration_minutes": int,
        "session_index": int,
        "metrics": dict,
        "rolling_stats": dict,
        "trends": dict,
        "flags": list,
        "tags": list
    },
    "rolling_stats_metric": {
        "window_size": int,
        "mean": float,
        "sd": float,
        "mean_minus_1sd": float,
        "mean_plus_1sd": float,
        "mean_minus_2sd": float,
        "mean_plus_2sd": float
    },
    "trends_metric": {
        "delta_vs_fixed": (float, type(None)),
        "pct_vs_fixed": (float, type(None)),
        "delta_vs_rolling": (float, type(None)),
        "pct_vs_rolling": (float, type(None)),
        "z_fixed": (float, type(None)),
        "z_rolling": (float, type(None)),
        "direction": str,
        "significance": str
    },
    "notes": {
        "method": str,
        "bands": str,
        "insufficient_band_rule": str
    }
}

def check_field_type(value: Any, expected_type: Any, field_path: str) -> List[str]:
    """Check if a field matches the expected type."""
    errors = []
    
    if isinstance(expected_type, tuple):
        # Multiple allowed types
        if not any(isinstance(value, t) if t != type(None) else value is None for t in expected_type):
            errors.append(f"{field_path}: Expected one of {expected_type}, got {type(value).__name__}")
    else:
        # Single type
        if not isinstance(value, expected_type):
            errors.append(f"{field_path}: Expected {expected_type.__name__}, got {type(value).__name__}")
    
    return errors

def check_structure(data: Dict, structure: Dict, path: str = "") -> List[str]:
    """Recursively check if data matches the expected structure."""
    errors = []
    
    for field, expected_type in structure.items():
        field_path = f"{path}.{field}" if path else field
        
        if field not in data:
            errors.append(f"Missing field: {field_path}")
            continue
        
        errors.extend(check_field_type(data[field], expected_type, field_path))
    
    # Check for unexpected fields
    for field in data:
        if field not in structure:
            errors.append(f"Unexpected field: {path}.{field}" if path else field)
    
    return errors

def test_baseline_endpoint():
    """Test the baseline endpoint structure."""
    print("=" * 60)
    print("BASELINE ENDPOINT STRUCTURE TEST")
    print("=" * 60)
    
    # Test different parameter combinations
    test_cases = [
        {
            "name": "Default parameters",
            "params": {"user_id": TEST_USER_ID}
        },
        {
            "name": "Custom m and n",
            "params": {"user_id": TEST_USER_ID, "m": 10, "n": 5}
        },
        {
            "name": "With max_sessions",
            "params": {"user_id": TEST_USER_ID, "max_sessions": 50}
        },
        {
            "name": "Custom metrics",
            "params": {"user_id": TEST_USER_ID, "metrics": "rmssd,sdnn"}
        },
        {
            "name": "All four default metrics",
            "params": {"user_id": TEST_USER_ID, "metrics": "rmssd,sdnn,sd2_sd1,mean_hr"}
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print("-" * 40)
        
        try:
            response = requests.get(API_URL, params=test_case['params'])
            
            if response.status_code != 200:
                print(f"❌ Failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                all_passed = False
                continue
            
            data = response.json()
            errors = []
            
            # Check top-level structure
            errors.extend(check_structure(data, EXPECTED_STRUCTURE["top_level"]))
            
            # Check fixed_baseline structure
            if "fixed_baseline" in data and isinstance(data["fixed_baseline"], dict):
                for metric, metric_data in data["fixed_baseline"].items():
                    if isinstance(metric_data, dict):
                        errors.extend(check_structure(
                            metric_data, 
                            EXPECTED_STRUCTURE["fixed_baseline_metric"],
                            f"fixed_baseline.{metric}"
                        ))
            
            # Check dynamic_baseline structure
            if "dynamic_baseline" in data and isinstance(data["dynamic_baseline"], list):
                if data["dynamic_baseline"]:  # If not empty
                    # Check first session as sample
                    session = data["dynamic_baseline"][0]
                    errors.extend(check_structure(
                        session,
                        EXPECTED_STRUCTURE["dynamic_session"],
                        "dynamic_baseline[0]"
                    ))
                    
                    # Check rolling_stats structure
                    if "rolling_stats" in session and isinstance(session["rolling_stats"], dict):
                        for metric, stats in session["rolling_stats"].items():
                            if isinstance(stats, dict):
                                errors.extend(check_structure(
                                    stats,
                                    EXPECTED_STRUCTURE["rolling_stats_metric"],
                                    f"dynamic_baseline[0].rolling_stats.{metric}"
                                ))
                    
                    # Check trends structure
                    if "trends" in session and isinstance(session["trends"], dict):
                        for metric, trend in session["trends"].items():
                            if isinstance(trend, dict):
                                errors.extend(check_structure(
                                    trend,
                                    EXPECTED_STRUCTURE["trends_metric"],
                                    f"dynamic_baseline[0].trends.{metric}"
                                ))
            
            # Check notes structure
            if "notes" in data and isinstance(data["notes"], dict):
                errors.extend(check_structure(data["notes"], EXPECTED_STRUCTURE["notes"], "notes"))
            
            # Report results
            if errors:
                print(f"❌ Structure validation failed:")
                for error in errors[:10]:  # Show first 10 errors
                    print(f"   - {error}")
                if len(errors) > 10:
                    print(f"   ... and {len(errors) - 10} more errors")
                all_passed = False
            else:
                print(f"✅ Structure validation passed")
                
                # Show summary of response
                print(f"   - Total sessions: {data.get('total_sessions', 0)}")
                print(f"   - Metrics: {data.get('metrics', [])}")
                print(f"   - Fixed baseline points: {data.get('m_points_actual', 0)}/{data.get('m_points_requested', 0)}")
                print(f"   - Rolling window: {data.get('n_points_actual', 0)}/{data.get('n_points_requested', 0)}")
                if data.get('warnings'):
                    print(f"   - Warnings: {data['warnings']}")
                
                # Show sample values
                if data.get('fixed_baseline', {}).get('rmssd', {}).get('mean'):
                    print(f"   - RMSSD fixed mean: {data['fixed_baseline']['rmssd']['mean']}")
                if data.get('dynamic_baseline') and len(data['dynamic_baseline']) > 0:
                    last_session = data['dynamic_baseline'][-1]
                    print(f"   - Last session index: {last_session.get('session_index', 'N/A')}")
                    if last_session.get('metrics', {}).get('rmssd'):
                        print(f"   - Last RMSSD value: {last_session['metrics']['rmssd']}")
        
        except requests.RequestException as e:
            print(f"❌ Request failed: {e}")
            all_passed = False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON response: {e}")
            all_passed = False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            all_passed = False
    
    # Final summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Structure matches specification exactly!")
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = test_baseline_endpoint()
    sys.exit(0 if success else 1)
