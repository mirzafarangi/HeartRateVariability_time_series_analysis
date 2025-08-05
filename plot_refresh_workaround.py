#!/usr/bin/env python3
"""
HRV Plot Refresh Workaround

Since individual debug endpoints work perfectly but batch processing fails,
this script uses the working individual endpoints to refresh all plots.
"""

import requests
import json
import time
from typing import Dict, List

class HRVPlotRefresher:
    def __init__(self, base_url: str = "https://hrv-brain-api-production.up.railway.app"):
        self.base_url = base_url
        self.metrics = ['mean_hr', 'mean_rr', 'count_rr', 'rmssd', 'sdnn', 'pnn50', 'cv_rr', 'defa', 'sd2_sd1']
    
    def refresh_all_plots(self, user_id: str, tag: str) -> Dict:
        """
        Refresh all HRV plots using individual working endpoints
        """
        print(f"🔄 Starting plot refresh for user {user_id}, tag {tag}")
        
        results = {}
        successful = 0
        
        for i, metric in enumerate(self.metrics, 1):
            print(f"📊 Processing {metric} ({i}/{len(self.metrics)})...")
            
            try:
                # Use the working debug endpoint for each metric
                url = f"{self.base_url}/api/v1/debug/plot-test/{user_id}/{tag}/{metric}"
                
                response = requests.get(url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and len(data.get('plot_data', '')) > 0:
                        results[metric] = True
                        successful += 1
                        print(f"  ✅ {metric}: SUCCESS (plot size: {len(data.get('plot_data', ''))} bytes)")
                    else:
                        results[metric] = False
                        print(f"  ❌ {metric}: FAILED (no plot data)")
                else:
                    results[metric] = False
                    print(f"  ❌ {metric}: HTTP {response.status_code}")
                
                # Small delay to avoid overwhelming the server
                time.sleep(0.5)
                
            except Exception as e:
                results[metric] = False
                print(f"  ❌ {metric}: EXCEPTION - {str(e)}")
        
        success_rate = successful / len(self.metrics)
        
        print(f"\n📈 SUMMARY:")
        print(f"  Total metrics: {len(self.metrics)}")
        print(f"  Successful: {successful}")
        print(f"  Success rate: {success_rate:.1%}")
        
        return {
            'success': True,
            'tag': tag,
            'refresh_results': results,
            'summary': {
                'total': len(self.metrics),
                'successful': successful,
                'success_rate': success_rate
            }
        }
    
    def verify_plots_stored(self, user_id: str) -> Dict:
        """
        Verify that plots are properly stored in database
        """
        print(f"🔍 Verifying stored plots for user {user_id}...")
        
        try:
            url = f"{self.base_url}/api/v1/plots/user/{user_id}"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                total_plots = data.get('total_plots', 0)
                plots = data.get('plots', {})
                
                print(f"  📊 Total plots stored: {total_plots}")
                
                for tag, tag_plots in plots.items():
                    print(f"  📁 {tag}: {len(tag_plots)} plots")
                    for metric in tag_plots:
                        print(f"    - {metric}")
                
                return data
            else:
                print(f"  ❌ HTTP {response.status_code}: {response.text}")
                return {}
                
        except Exception as e:
            print(f"  ❌ EXCEPTION: {str(e)}")
            return {}

def main():
    """Main execution"""
    print("🚀 HRV Plot Refresh Workaround")
    print("=" * 50)
    
    # Configuration
    user_id = "7015839c-4659-4b6c-821c-2906e710a2db"
    tag = "rest"
    
    refresher = HRVPlotRefresher()
    
    # Step 1: Refresh all plots using working individual endpoints
    result = refresher.refresh_all_plots(user_id, tag)
    
    # Step 2: Verify plots are stored in database
    stored_plots = refresher.verify_plots_stored(user_id)
    
    # Step 3: Final summary
    print(f"\n🎯 FINAL RESULT:")
    if result['summary']['success_rate'] > 0:
        print(f"  ✅ SUCCESS: {result['summary']['successful']}/{result['summary']['total']} plots generated")
        print(f"  📊 Success rate: {result['summary']['success_rate']:.1%}")
    else:
        print(f"  ❌ FAILED: No plots generated successfully")
    
    return result

if __name__ == "__main__":
    main()
