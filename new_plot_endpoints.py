"""
New Plot Endpoints for HRV Brain API
Version: 4.0.0 - On-Demand Plot Generation Architecture

This module implements the new on-demand plot generation system:
- Rest Baseline Trends (RMSSD/SDNN for all rest sessions)
- Sleep Event Trends (RMSSD/SDNN for specific event_id)
- Sleep Baseline Trends (RMSSD/SDNN averaged per event_id)
- Sleep Event ID listing (last N sleep events)

All plots are generated on-demand only, no auto-generation on session upload.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import numpy as np
from plot_generator import HRVPlotGenerator

logger = logging.getLogger(__name__)

class OnDemandPlotService:
    """Service for on-demand HRV plot generation"""
    
    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
        self.plot_generator = HRVPlotGenerator()
    
    def get_sleep_event_ids(self, user_id: str, limit: int = 7) -> List[int]:
        """Get last N sleep event IDs for user, sorted descending"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT DISTINCT event_id 
                        FROM sessions 
                        WHERE user_id = %s 
                        AND tag = 'sleep' 
                        AND event_id > 0
                        ORDER BY event_id DESC 
                        LIMIT %s
                    """, (user_id, limit))
                    
                    results = cursor.fetchall()
                    return [row['event_id'] for row in results]
                    
        except Exception as e:
            logger.error(f"Error fetching sleep event IDs for user {user_id}: {str(e)}")
            return []
        finally:
            if 'conn' in locals():
                self.connection_pool.putconn(conn)
    
    def get_rest_sessions(self, user_id: str) -> List[Dict]:
        """Get all rest sessions for user"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT session_id, user_id, tag, subtag, event_id,
                               recorded_at, mean_hr, mean_rr, count_rr, 
                               rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                        FROM sessions 
                        WHERE user_id = %s 
                        AND tag = 'rest'
                        AND status = 'completed'
                        ORDER BY recorded_at ASC
                    """, (user_id,))
                    
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Error fetching rest sessions for user {user_id}: {str(e)}")
            return []
        finally:
            if 'conn' in locals():
                self.connection_pool.putconn(conn)
    
    def get_sleep_sessions_by_event(self, user_id: str, event_id: int) -> List[Dict]:
        """Get all sleep sessions for specific event_id"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT session_id, user_id, tag, subtag, event_id,
                               recorded_at, mean_hr, mean_rr, count_rr, 
                               rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                        FROM sessions 
                        WHERE user_id = %s 
                        AND tag = 'sleep'
                        AND event_id = %s
                        AND status = 'completed'
                        ORDER BY recorded_at ASC
                    """, (user_id, event_id))
                    
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Error fetching sleep sessions for user {user_id}, event {event_id}: {str(e)}")
            return []
        finally:
            if 'conn' in locals():
                self.connection_pool.putconn(conn)
    
    def get_sleep_baseline_data(self, user_id: str) -> List[Dict]:
        """Get sleep baseline data - average metrics per event_id"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            event_id,
                            MIN(recorded_at) as event_date,
                            COUNT(*) as session_count,
                            AVG(mean_hr) as avg_mean_hr,
                            AVG(mean_rr) as avg_mean_rr,
                            AVG(count_rr) as avg_count_rr,
                            AVG(rmssd) as avg_rmssd,
                            AVG(sdnn) as avg_sdnn,
                            AVG(pnn50) as avg_pnn50,
                            AVG(cv_rr) as avg_cv_rr,
                            AVG(defa) as avg_defa,
                            AVG(sd2_sd1) as avg_sd2_sd1
                        FROM sessions 
                        WHERE user_id = %s 
                        AND tag = 'sleep'
                        AND event_id > 0
                        AND status = 'completed'
                        GROUP BY event_id
                        ORDER BY event_id ASC
                    """, (user_id,))
                    
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Error fetching sleep baseline data for user {user_id}: {str(e)}")
            return []
        finally:
            if 'conn' in locals():
                self.connection_pool.putconn(conn)
    
    def generate_rest_baseline_plots(self, user_id: str) -> Dict[str, Dict]:
        """Generate Rest Baseline Trends (RMSSD + SDNN)"""
        logger.info(f"Generating rest baseline plots for user {user_id}")
        
        # Get rest sessions
        sessions = self.get_rest_sessions(user_id)
        if not sessions:
            return {
                'success': False,
                'error': 'No rest sessions found',
                'plots': {},
                'sessions_count': 0
            }
        
        logger.info(f"Found {len(sessions)} rest sessions for user {user_id}")
        
        # Convert sessions to format expected by plot generator (COMPLETE DATA STRUCTURE)
        sessions_data = []
        for session in sessions:
            # Create complete session data structure with ALL required fields
            session_dict = {
                'session_id': session.get('session_id'),
                'tag': 'rest',  # ✅ CRITICAL: Add missing 'tag' field
                'subtag': session.get('subtag'),
                'recorded_at': session['recorded_at'].isoformat() if hasattr(session['recorded_at'], 'isoformat') else str(session['recorded_at']),
                'hrv_metrics': {  # ✅ CRITICAL: Include ALL HRV metrics, not just one
                    'mean_hr': float(session['mean_hr']) if session.get('mean_hr') is not None else None,
                    'mean_rr': float(session['mean_rr']) if session.get('mean_rr') is not None else None,
                    'count_rr': int(session['count_rr']) if session.get('count_rr') is not None else None,
                    'rmssd': float(session['rmssd']) if session.get('rmssd') is not None else None,
                    'sdnn': float(session['sdnn']) if session.get('sdnn') is not None else None,
                    'pnn50': float(session['pnn50']) if session.get('pnn50') is not None else None,
                    'cv_rr': float(session['cv_rr']) if session.get('cv_rr') is not None else None,
                    'defa': float(session['defa']) if session.get('defa') is not None else None,
                    'sd2_sd1': float(session['sd2_sd1']) if session.get('sd2_sd1') is not None else None
                }
            }
            sessions_data.append(session_dict)
        
        if not sessions_data:
            return {
                'success': False,
                'error': 'No valid rest sessions found',
                'plots': {},
                'sessions_count': 0
            }
        
        plots = {}
        metrics = ['rmssd', 'sdnn']
        
        for metric in metrics:
            try:
                logger.info(f"Generating {metric} plot for {len(sessions_data)} rest sessions")
                
                # Generate plot using COMPLETE session data structure
                plot_base64, stats = self.plot_generator.generate_trend_plot(
                    sessions_data, [], metric, 'rest', 'Baseline'
                )
                
                plots[metric] = {
                    'success': True,
                    'plot_data': plot_base64,
                    'metadata': {
                        'metric': metric,
                        'tag': 'rest',
                        'type': 'baseline',
                        'data_points': len(sessions_data),
                        'statistics': stats
                    }
                }
                
            except Exception as e:
                logger.error(f"Error generating {metric} rest baseline plot: {str(e)}")
                plots[metric] = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'success': True,
            'plots': plots,
            'sessions_count': len(sessions)
        }
    
    def generate_sleep_event_plots(self, user_id: str, event_id: int) -> Dict[str, Dict]:
        """Generate Sleep Event Trends (RMSSD + SDNN for specific event_id)"""
        logger.info(f"Generating sleep event plots for user {user_id}, event {event_id}")
        
        # Get sleep sessions for this event
        sessions = self.get_sleep_sessions_by_event(user_id, event_id)
        if not sessions:
            return {
                'success': False,
                'error': f'No sleep sessions found for event {event_id}',
                'plots': {},
                'sessions_count': 0
            }
        
        logger.info(f"Found {len(sessions)} sleep sessions for user {user_id}, event {event_id}")
        
        # Convert sessions to format expected by plot generator (COMPLETE DATA STRUCTURE)
        sessions_data = []
        for session in sessions:
            # Create complete session data structure with ALL required fields
            session_dict = {
                'session_id': session.get('session_id'),
                'tag': 'sleep',  # ✅ CRITICAL: Add missing 'tag' field
                'subtag': session.get('subtag'),
                'recorded_at': session['recorded_at'].isoformat() if hasattr(session['recorded_at'], 'isoformat') else str(session['recorded_at']),
                'hrv_metrics': {  # ✅ CRITICAL: Include ALL HRV metrics, not just one
                    'mean_hr': float(session['mean_hr']) if session.get('mean_hr') is not None else None,
                    'mean_rr': float(session['mean_rr']) if session.get('mean_rr') is not None else None,
                    'count_rr': int(session['count_rr']) if session.get('count_rr') is not None else None,
                    'rmssd': float(session['rmssd']) if session.get('rmssd') is not None else None,
                    'sdnn': float(session['sdnn']) if session.get('sdnn') is not None else None,
                    'pnn50': float(session['pnn50']) if session.get('pnn50') is not None else None,
                    'cv_rr': float(session['cv_rr']) if session.get('cv_rr') is not None else None,
                    'defa': float(session['defa']) if session.get('defa') is not None else None,
                    'sd2_sd1': float(session['sd2_sd1']) if session.get('sd2_sd1') is not None else None
                }
            }
            sessions_data.append(session_dict)
        
        if not sessions_data:
            return {
                'success': False,
                'error': f'No valid sleep sessions found for event {event_id}',
                'plots': {},
                'sessions_count': 0
            }
        
        plots = {}
        metrics = ['rmssd', 'sdnn']
        
        for metric in metrics:
            try:
                logger.info(f"Generating {metric} plot for {len(sessions_data)} sleep sessions (event {event_id})")
                
                # Generate plot using COMPLETE session data structure
                plot_base64, stats = self.plot_generator.generate_trend_plot(
                    sessions_data, [], metric, 'sleep', f'Event {event_id}'
                )
                
                plots[metric] = {
                    'success': True,
                    'plot_data': plot_base64,
                    'metadata': {
                        'metric': metric,
                        'tag': 'sleep',
                        'type': 'event',
                        'event_id': event_id,
                        'data_points': len(sessions_data),
                        'statistics': stats
                    }
                }
                
            except Exception as e:
                logger.error(f"Error generating {metric} sleep event plot: {str(e)}")
                plots[metric] = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'success': True,
            'plots': plots,
            'event_id': event_id,
            'sessions_count': len(sessions)
        }
    
    def generate_sleep_baseline_plots(self, user_id: str) -> Dict[str, Dict]:
        """Generate Sleep Baseline Trends (RMSSD + SDNN averaged per event_id)"""
        logger.info(f"Generating sleep baseline plots for user {user_id}")
        
        # Get sleep baseline data (averaged per event)
        baseline_data = self.get_sleep_baseline_data(user_id)
        if not baseline_data:
            return {
                'success': False,
                'error': 'No sleep baseline data found',
                'plots': {}
            }
        
        plots = {}
        metrics = ['rmssd', 'sdnn']
        
        for metric in metrics:
            try:
                logger.info(f"Generating {metric} baseline plot for {len(baseline_data)} sleep events")
                
                # Convert baseline data to format expected by plot generator (COMPLETE DATA STRUCTURE)
                baseline_sessions = []
                avg_metric_key = f'avg_{metric}'
                
                for event_data in baseline_data:
                    if event_data.get(avg_metric_key) is not None:
                        # Create complete session data structure with ALL required fields
                        session_dict = {
                            'session_id': f"baseline_event_{event_data.get('event_id', 'unknown')}",
                            'tag': 'sleep',  # ✅ CRITICAL: Add missing 'tag' field
                            'subtag': 'baseline',
                            'recorded_at': event_data['event_date'].isoformat() if hasattr(event_data['event_date'], 'isoformat') else str(event_data['event_date']),
                            'hrv_metrics': {  # ✅ CRITICAL: Include ALL HRV metrics from baseline data
                                'mean_hr': float(event_data.get('avg_mean_hr')) if event_data.get('avg_mean_hr') is not None else None,
                                'mean_rr': float(event_data.get('avg_mean_rr')) if event_data.get('avg_mean_rr') is not None else None,
                                'count_rr': float(event_data.get('avg_count_rr')) if event_data.get('avg_count_rr') is not None else None,
                                'rmssd': float(event_data.get('avg_rmssd')) if event_data.get('avg_rmssd') is not None else None,
                                'sdnn': float(event_data.get('avg_sdnn')) if event_data.get('avg_sdnn') is not None else None,
                                'pnn50': float(event_data.get('avg_pnn50')) if event_data.get('avg_pnn50') is not None else None,
                                'cv_rr': float(event_data.get('avg_cv_rr')) if event_data.get('avg_cv_rr') is not None else None,
                                'defa': float(event_data.get('avg_defa')) if event_data.get('avg_defa') is not None else None,
                                'sd2_sd1': float(event_data.get('avg_sd2_sd1')) if event_data.get('avg_sd2_sd1') is not None else None
                            }
                        }
                        baseline_sessions.append(session_dict)
                
                if not baseline_sessions:
                    plots[metric] = {
                        'success': False,
                        'error': f'No {metric} baseline data found'
                    }
                    continue
                
                # Generate plot using COMPLETE session data structure
                plot_base64, stats = self.plot_generator.generate_trend_plot(
                    baseline_sessions, [], metric, 'sleep', 'Baseline'
                )
                
                plots[metric] = {
                    'success': True,
                    'plot_data': plot_base64,
                    'metadata': {
                        'metric': metric,
                        'tag': 'sleep',
                        'type': 'baseline',
                        'data_points': len(baseline_sessions),
                        'events_count': len(baseline_data),
                        'statistics': stats
                    }
                }
                
            except Exception as e:
                logger.error(f"Error generating {metric} sleep baseline plot: {str(e)}")
                plots[metric] = {
                    'success': False,
                    'error': str(e)
                }
        
        return {
            'success': True,
            'plots': plots,
            'events_count': len(baseline_data)
        }
