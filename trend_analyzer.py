"""
HRV Trend Analysis Module
Version: 1.0.0
Date: 2025-08-07
Source: polish_architecture.md

Implements centralized trend analysis logic for RMSSD-based HRV visualizations.
All statistical calculations (rolling average, baseline, SD bands, percentiles) 
are performed server-side and returned as structured JSON.
"""

import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """
    Centralized trend analysis for HRV data
    Implements the exact specifications from polish_architecture.md
    """
    
    def __init__(self, rolling_window: int = 3, min_percentile_sessions: int = 30):
        self.rolling_window = rolling_window
        self.min_percentile_sessions = min_percentile_sessions
    
    def analyze_rest_trend(self, sessions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze non-sleep session trend
        
        Args:
            sessions: List of session dictionaries with 'recorded_at' and 'rmssd'
            
        Returns:
            Unified JSON response per architecture spec
        """
        if not sessions:
            return self._empty_response()
        
        # Sort by date
        sorted_sessions = sorted(sessions, key=lambda x: x['recorded_at'])
        
        # Extract raw data points
        raw_data = [
            {
                'date': self._format_date(session['recorded_at']),
                'rmssd': float(session['rmssd']) if session['rmssd'] is not None else None
            }
            for session in sorted_sessions
            if session['rmssd'] is not None
        ]
        
        # Filter out None values
        raw_data = [point for point in raw_data if point['rmssd'] is not None]
        
        if not raw_data:
            return self._empty_response()
        
        result = {
            'raw': raw_data
        }
        
        # Rolling average (if >= 3 points)
        if len(raw_data) >= self.rolling_window:
            result['rolling_avg'] = self._calculate_rolling_average(raw_data)
        
        # No baseline for non-sleep data (per architecture)
        # No SD bands for non-sleep data (per architecture)
        
        # Percentiles (optional if >= 30 sessions)
        if len(raw_data) >= self.min_percentile_sessions:
            rmssd_values = [point['rmssd'] for point in raw_data]
            result['percentile_10'] = float(np.percentile(rmssd_values, 10))
            result['percentile_90'] = float(np.percentile(rmssd_values, 90))
        
        return result
    
    def analyze_sleep_interval_trend(self, sessions: List[Dict], all_sleep_sessions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze sleep intervals trend (all intervals of last event)
        
        Args:
            sessions: Sleep intervals from the latest event
            all_sleep_sessions: All sleep sessions for baseline calculation
            
        Returns:
            Unified JSON response per architecture spec
        """
        if not sessions:
            return self._empty_response()
        
        # Sort by date
        sorted_sessions = sorted(sessions, key=lambda x: x['recorded_at'])
        
        # Extract raw data points
        raw_data = [
            {
                'date': self._format_date(session['recorded_at']),
                'rmssd': float(session['rmssd']) if session['rmssd'] is not None else None
            }
            for session in sorted_sessions
            if session['rmssd'] is not None
        ]
        
        # Filter out None values
        raw_data = [point for point in raw_data if point['rmssd'] is not None]
        
        if not raw_data:
            return self._empty_response()
        
        result = {
            'raw': raw_data
        }
        
        # Rolling average
        if len(raw_data) >= self.rolling_window:
            result['rolling_avg'] = self._calculate_rolling_average(raw_data)
        
        # Sleep 7-day baseline (computed from all sleep data)
        baseline = self._calculate_sleep_baseline(all_sleep_sessions)
        if baseline is not None:
            result['baseline'] = baseline
            
            # SD Band: ±1 SD from 7-day baseline
            sd_band = self._calculate_sd_band(all_sleep_sessions, baseline)
            if sd_band:
                result['sd_band'] = sd_band
        
        # Percentiles (optional if enough data)
        if len(raw_data) >= self.min_percentile_sessions:
            rmssd_values = [point['rmssd'] for point in raw_data]
            result['percentile_10'] = float(np.percentile(rmssd_values, 10))
            result['percentile_90'] = float(np.percentile(rmssd_values, 90))
        
        return result
    
    def analyze_sleep_event_trend(self, events: List[Dict]) -> Dict[str, Any]:
        """
        Analyze aggregated sleep event trend
        
        Args:
            events: List of aggregated event dictionaries with 'event_start' and 'avg_rmssd'
            
        Returns:
            Unified JSON response per architecture spec
        """
        if not events:
            return self._empty_response()
        
        # Sort by event start date
        sorted_events = sorted(events, key=lambda x: x['event_start'])
        
        # Extract raw data points (using event averages)
        raw_data = [
            {
                'date': self._format_date(event['event_start']),
                'rmssd': float(event['avg_rmssd']) if event['avg_rmssd'] is not None else None
            }
            for event in sorted_events
            if event['avg_rmssd'] is not None
        ]
        
        # Filter out None values
        raw_data = [point for point in raw_data if point['rmssd'] is not None]
        
        if not raw_data:
            return self._empty_response()
        
        result = {
            'raw': raw_data
        }
        
        # Rolling average over event means
        if len(raw_data) >= self.rolling_window:
            result['rolling_avg'] = self._calculate_rolling_average(raw_data)
        
        # Optional 7-event baseline
        if len(raw_data) >= 7:
            recent_events = raw_data[-7:]  # Last 7 events
            baseline_values = [point['rmssd'] for point in recent_events]
            result['baseline'] = float(np.mean(baseline_values))
            
            # SD Band: ±1 SD of event averages
            if len(baseline_values) > 1:
                std_dev = float(np.std(baseline_values))
                result['sd_band'] = {
                    'upper': result['baseline'] + std_dev,
                    'lower': result['baseline'] - std_dev
                }
        
        # Percentiles (only if >= 30 events)
        if len(raw_data) >= self.min_percentile_sessions:
            rmssd_values = [point['rmssd'] for point in raw_data]
            result['percentile_10'] = float(np.percentile(rmssd_values, 10))
            result['percentile_90'] = float(np.percentile(rmssd_values, 90))
        
        return result
    
    def _calculate_rolling_average(self, data: List[Dict]) -> List[Dict]:
        """Calculate trailing rolling average (N=3)"""
        if len(data) < self.rolling_window:
            return []
        
        rolling_avg = []
        for i in range(self.rolling_window - 1, len(data)):
            window_values = [data[j]['rmssd'] for j in range(i - self.rolling_window + 1, i + 1)]
            avg_value = np.mean(window_values)
            
            rolling_avg.append({
                'date': data[i]['date'],
                'rmssd': float(avg_value)
            })
        
        return rolling_avg
    
    def _calculate_sleep_baseline(self, all_sleep_sessions: List[Dict]) -> Optional[float]:
        """Calculate 7-day sleep baseline from all sleep sessions"""
        if not all_sleep_sessions:
            return None
        
        # Get sessions from last 7 days
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        
        recent_sessions = [
            session for session in all_sleep_sessions
            if self._parse_date(session['recorded_at']) >= seven_days_ago
            and session['rmssd'] is not None
        ]
        
        if not recent_sessions:
            return None
        
        rmssd_values = [float(session['rmssd']) for session in recent_sessions]
        return float(np.mean(rmssd_values))
    
    def _calculate_sd_band(self, all_sleep_sessions: List[Dict], baseline: float) -> Optional[Dict[str, float]]:
        """Calculate ±1 SD band around 7-day baseline"""
        if not all_sleep_sessions:
            return None
        
        # Get sessions from last 7 days
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        
        recent_sessions = [
            session for session in all_sleep_sessions
            if self._parse_date(session['recorded_at']) >= seven_days_ago
            and session['rmssd'] is not None
        ]
        
        if len(recent_sessions) < 2:
            return None
        
        rmssd_values = [float(session['rmssd']) for session in recent_sessions]
        std_dev = float(np.std(rmssd_values))
        
        return {
            'upper': baseline + std_dev,
            'lower': baseline - std_dev
        }
    
    def _format_date(self, date_input: Any) -> str:
        """Format date consistently as YYYY-MM-DD"""
        if isinstance(date_input, str):
            # Parse ISO format and extract date
            dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        elif isinstance(date_input, datetime):
            return date_input.strftime('%Y-%m-%d')
        else:
            return str(date_input)
    
    def _parse_date(self, date_input: Any) -> datetime:
        """Parse date input to timezone-aware datetime object"""
        if isinstance(date_input, str):
            # Handle ISO format with Z suffix
            if date_input.endswith('Z'):
                return datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(date_input)
                # If naive datetime, assume UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        elif isinstance(date_input, datetime):
            # If naive datetime, assume UTC
            if date_input.tzinfo is None:
                return date_input.replace(tzinfo=timezone.utc)
            return date_input
        else:
            raise ValueError(f"Cannot parse date: {date_input}")
    
    def _empty_response(self) -> Dict[str, Any]:
        """Return empty response structure"""
        return {
            'raw': []
        }

# Global analyzer instance
trend_analyzer = TrendAnalyzer()
