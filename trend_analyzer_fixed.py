"""
HRV Trend Analysis Module - FIXED VERSION with Timestamp Precision
Version: 1.1.0 - Timestamp Precision Fix
Date: 2025-08-07
Source: polish_architecture.md + timestamp precision fix

Implements centralized trend analysis logic for RMSSD-based HRV visualizations.
All statistical calculations (rolling average, baseline, SD bands, percentiles) 
are performed server-side and returned as structured JSON.

CRITICAL FIX: Uses full timestamp precision instead of date-only format to fix vertical line bug.
"""

import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """
    Centralized trend analysis for HRV data - FIXED VERSION
    Implements timestamp precision to fix chronological plotting issues
    """
    
    def __init__(self, rolling_window: int = 3, min_percentile_sessions: int = 5):
        self.rolling_window = rolling_window
        self.min_percentile_sessions = min_percentile_sessions  # Reduced from 30 to 5 for testing
    
    def analyze_rest_trend(self, sessions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze non-sleep session trend - FIXED with timestamp precision
        
        Args:
            sessions: List of session dictionaries with 'recorded_at' and 'rmssd'
            
        Returns:
            Unified JSON response per architecture spec with timestamp precision
        """
        if not sessions:
            return self._empty_response()
        
        # Sort by timestamp
        sorted_sessions = sorted(sessions, key=lambda x: x['recorded_at'])
        
        # Extract raw data points with timestamp precision
        raw_data = []
        for session in sorted_sessions:
            if session['rmssd'] is not None:
                # Use full ISO timestamp instead of date-only format
                timestamp = session['recorded_at']
                if isinstance(timestamp, str):
                    # Keep full ISO timestamp for precise X-axis scaling
                    formatted_timestamp = timestamp
                else:
                    # Convert datetime to ISO format with microseconds
                    formatted_timestamp = timestamp.isoformat()
                
                raw_data.append({
                    'timestamp': formatted_timestamp,  # Full precision timestamp
                    'rmssd': float(session['rmssd'])
                })
        
        if not raw_data:
            return self._empty_response()
        
        # Calculate rolling average
        rolling_avg_data = []
        if len(raw_data) >= self.rolling_window:
            for i in range(self.rolling_window - 1, len(raw_data)):
                window_values = [raw_data[j]['rmssd'] for j in range(i - self.rolling_window + 1, i + 1)]
                avg_value = np.mean(window_values)
                
                rolling_avg_data.append({
                    'timestamp': raw_data[i]['timestamp'],
                    'rmssd': float(avg_value)
                })
        
        # Calculate percentiles (reduced threshold)
        rmssd_values = [point['rmssd'] for point in raw_data]
        percentile_10 = None
        percentile_90 = None
        if len(rmssd_values) >= self.min_percentile_sessions:
            percentile_10 = float(np.percentile(rmssd_values, 10))
            percentile_90 = float(np.percentile(rmssd_values, 90))
        
        # Build response
        response = {'raw': raw_data}
        
        # Add optional fields
        if rolling_avg_data:
            response['rolling_avg'] = rolling_avg_data
        
        if percentile_10 is not None and percentile_90 is not None:
            response['percentile_10'] = percentile_10
            response['percentile_90'] = percentile_90
        
        return response
    
    def analyze_sleep_interval_trend(self, sessions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze sleep intervals trend - FIXED with timestamp precision
        
        Args:
            sessions: List of session dictionaries with 'recorded_at' and 'rmssd'
            
        Returns:
            Unified JSON response with timestamp precision
        """
        if not sessions:
            return self._empty_response()
        
        # Sort by timestamp
        sorted_sessions = sorted(sessions, key=lambda x: x['recorded_at'])
        
        # Extract raw data points with timestamp precision
        raw_data = []
        for session in sorted_sessions:
            if session['rmssd'] is not None:
                # Use full ISO timestamp instead of date-only format
                timestamp = session['recorded_at']
                if isinstance(timestamp, str):
                    formatted_timestamp = timestamp
                else:
                    formatted_timestamp = timestamp.isoformat()
                
                raw_data.append({
                    'timestamp': formatted_timestamp,
                    'rmssd': float(session['rmssd'])
                })
        
        if not raw_data:
            return self._empty_response()
        
        # Calculate rolling average
        rolling_avg_data = []
        if len(raw_data) >= self.rolling_window:
            for i in range(self.rolling_window - 1, len(raw_data)):
                window_values = [raw_data[j]['rmssd'] for j in range(i - self.rolling_window + 1, i + 1)]
                avg_value = np.mean(window_values)
                
                rolling_avg_data.append({
                    'timestamp': raw_data[i]['timestamp'],
                    'rmssd': float(avg_value)
                })
        
        # Calculate baseline (7-day sleep average - simplified)
        rmssd_values = [point['rmssd'] for point in raw_data]
        baseline = float(np.mean(rmssd_values)) if rmssd_values else None
        
        # Calculate SD band (±1 SD from baseline)
        sd_band = None
        if baseline is not None and len(rmssd_values) >= 2:
            std_dev = float(np.std(rmssd_values, ddof=1))
            sd_band = {
                'upper': baseline + std_dev,
                'lower': baseline - std_dev
            }
        
        # Calculate percentiles (reduced threshold)
        percentile_10 = None
        percentile_90 = None
        if len(rmssd_values) >= self.min_percentile_sessions:
            percentile_10 = float(np.percentile(rmssd_values, 10))
            percentile_90 = float(np.percentile(rmssd_values, 90))
        
        # Build response
        response = {'raw': raw_data}
        
        # Add optional fields
        if rolling_avg_data:
            response['rolling_avg'] = rolling_avg_data
        
        if baseline is not None:
            response['baseline'] = baseline
        
        if sd_band is not None:
            response['sd_band'] = sd_band
        
        if percentile_10 is not None and percentile_90 is not None:
            response['percentile_10'] = percentile_10
            response['percentile_90'] = percentile_90
        
        return response
    
    def analyze_sleep_event_trend(self, events: List[Dict]) -> Dict[str, Any]:
        """
        Analyze aggregated sleep event trend - FIXED with timestamp precision
        
        Args:
            events: List of event dictionaries with 'event_start' and aggregated metrics
            
        Returns:
            Unified JSON response with timestamp precision
        """
        if not events:
            return self._empty_response()
        
        # Sort by event start timestamp
        sorted_events = sorted(events, key=lambda x: x.get('event_start', x.get('recorded_at', '')))
        
        # Extract raw data points with timestamp precision
        raw_data = []
        for event in sorted_events:
            rmssd_value = event.get('avg_rmssd') or event.get('rmssd')
            if rmssd_value is not None:
                # Use event_start or recorded_at timestamp
                timestamp = event.get('event_start') or event.get('recorded_at')
                if isinstance(timestamp, str):
                    formatted_timestamp = timestamp
                else:
                    formatted_timestamp = timestamp.isoformat()
                
                raw_data.append({
                    'timestamp': formatted_timestamp,
                    'rmssd': float(rmssd_value)
                })
        
        if not raw_data:
            return self._empty_response()
        
        # Calculate rolling average over events
        rolling_avg_data = []
        if len(raw_data) >= self.rolling_window:
            for i in range(self.rolling_window - 1, len(raw_data)):
                window_values = [raw_data[j]['rmssd'] for j in range(i - self.rolling_window + 1, i + 1)]
                avg_value = np.mean(window_values)
                
                rolling_avg_data.append({
                    'timestamp': raw_data[i]['timestamp'],
                    'rmssd': float(avg_value)
                })
        
        # Calculate baseline (7-event baseline)
        rmssd_values = [point['rmssd'] for point in raw_data]
        baseline = None
        if len(rmssd_values) >= 7:  # 7-event baseline
            baseline = float(np.mean(rmssd_values[-7:]))  # Last 7 events
        
        # Calculate SD band (±1 SD of event averages)
        sd_band = None
        if baseline is not None and len(rmssd_values) >= 2:
            std_dev = float(np.std(rmssd_values, ddof=1))
            sd_band = {
                'upper': baseline + std_dev,
                'lower': baseline - std_dev
            }
        
        # Calculate percentiles (reduced threshold)
        percentile_10 = None
        percentile_90 = None
        if len(rmssd_values) >= self.min_percentile_sessions:
            percentile_10 = float(np.percentile(rmssd_values, 10))
            percentile_90 = float(np.percentile(rmssd_values, 90))
        
        # Build response
        response = {'raw': raw_data}
        
        # Add optional fields
        if rolling_avg_data:
            response['rolling_avg'] = rolling_avg_data
        
        if baseline is not None:
            response['baseline'] = baseline
        
        if sd_band is not None:
            response['sd_band'] = sd_band
        
        if percentile_10 is not None and percentile_90 is not None:
            response['percentile_10'] = percentile_10
            response['percentile_90'] = percentile_90
        
        return response
    
    def analyze_test_sleep_interval(self, sessions: List[Dict]) -> Dict[str, Any]:
        """
        Test-specific sleep interval analysis with full timestamp precision
        Uses 1-second accuracy for X-axis scaling and reduced thresholds for testing
        
        Args:
            sessions: List of session dictionaries with 'recorded_at' (full ISO timestamp) and 'rmssd'
            
        Returns:
            Unified JSON response with timestamp precision
        """
        if not sessions:
            return self._empty_response()
        
        # Sort by full timestamp
        sorted_sessions = sorted(sessions, key=lambda x: x['recorded_at'])
        
        # Extract raw data points with full timestamp precision
        raw_data = []
        for session in sorted_sessions:
            # Use full ISO timestamp instead of date-only format
            timestamp = session['recorded_at']
            if isinstance(timestamp, str):
                # Keep full ISO timestamp for precise X-axis scaling
                formatted_timestamp = timestamp
            else:
                formatted_timestamp = timestamp.isoformat()
            
            raw_data.append({
                'timestamp': formatted_timestamp,  # Full precision timestamp
                'rmssd': float(session['rmssd']) if session['rmssd'] is not None else None
            })
        
        # Filter out None values
        valid_data = [point for point in raw_data if point['rmssd'] is not None]
        
        if not valid_data:
            return self._empty_response()
        
        # Calculate rolling average (reduced window for testing)
        rolling_avg_data = []
        test_window = min(3, len(valid_data))  # Adaptive window for small datasets
        
        if len(valid_data) >= test_window:
            for i in range(test_window - 1, len(valid_data)):
                window_values = [valid_data[j]['rmssd'] for j in range(i - test_window + 1, i + 1)]
                avg_value = np.mean(window_values)
                
                rolling_avg_data.append({
                    'timestamp': valid_data[i]['timestamp'],
                    'rmssd': float(avg_value)
                })
        
        # Calculate baseline (7-day sleep average - simplified for test)
        rmssd_values = [point['rmssd'] for point in valid_data]
        baseline = float(np.mean(rmssd_values)) if rmssd_values else None
        
        # Calculate SD band (±1 SD from baseline)
        sd_band = None
        if baseline is not None and len(rmssd_values) >= 2:
            std_dev = float(np.std(rmssd_values, ddof=1))
            sd_band = {
                'upper': baseline + std_dev,
                'lower': baseline - std_dev
            }
        
        # Calculate percentiles (reduced threshold: 5 instead of 30)
        percentile_10 = None
        percentile_90 = None
        if len(rmssd_values) >= 5:  # Reduced from 30 to 5 for testing
            percentile_10 = float(np.percentile(rmssd_values, 10))
            percentile_90 = float(np.percentile(rmssd_values, 90))
        
        # Build response
        response = {
            'raw': valid_data,  # Using timestamp precision
            'message': f'Test mode: {len(valid_data)} sleep intervals with timestamp precision'
        }
        
        # Add optional fields
        if rolling_avg_data:
            response['rolling_avg'] = rolling_avg_data
        
        if baseline is not None:
            response['baseline'] = baseline
        
        if sd_band is not None:
            response['sd_band'] = sd_band
        
        if percentile_10 is not None and percentile_90 is not None:
            response['percentile_10'] = percentile_10
            response['percentile_90'] = percentile_90
        
        return response
    
    def _empty_response(self) -> Dict[str, Any]:
        """Return empty response structure"""
        return {
            'raw': []
        }

# Global analyzer instance with timestamp precision fix
trend_analyzer_fixed = TrendAnalyzer()
