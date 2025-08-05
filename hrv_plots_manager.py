"""
HRV Plots Database Manager

Handles all database operations for persistent HRV plot storage.
Implements the new architecture where plots are generated once and stored in DB.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Any
import json
import logging
from datetime import datetime
from uuid import UUID

# Import required modules at top level to avoid circular import issues
try:
    from plot_generator import generate_hrv_plot
except ImportError:
    generate_hrv_plot = None
    
try:
    from app import get_sessions_data_for_plot
except ImportError:
    get_sessions_data_for_plot = None

logger = logging.getLogger(__name__)

class HRVPlotsManager:
    """Manages HRV plots in the database"""
    
    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
    
    def upsert_plot(self, 
                   user_id: str,
                   tag: str, 
                   metric: str,
                   plot_image_base64: str,
                   plot_metadata: Dict[str, Any],
                   data_points_count: int,
                   date_range_start: Optional[datetime] = None,
                   date_range_end: Optional[datetime] = None) -> Optional[str]:
        """
        Insert or update a plot in the database
        
        Args:
            user_id: User UUID
            tag: Session tag (rest, sleep, etc.)
            metric: HRV metric name
            plot_image_base64: Base64 encoded PNG image
            plot_metadata: Plot metadata including statistics
            data_points_count: Number of data points in plot
            date_range_start: Start date of data range
            date_range_end: End date of data range
            
        Returns:
            Plot ID if successful, None if failed
        """
        try:
            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            
            # Extract statistics from metadata
            stats = plot_metadata.get('statistics', {})
            stat_mean = stats.get('mean')
            stat_std = stats.get('std') 
            stat_min = stats.get('min')
            stat_max = stats.get('max')
            stat_p10 = stats.get('p10')
            stat_p90 = stats.get('p90')
            
            # Use direct SQL instead of function to identify exact issue
            cur.execute("""
                INSERT INTO public.hrv_plots (
                    user_id, tag, metric, plot_image_base64, plot_metadata,
                    data_points_count, date_range_start, date_range_end,
                    stat_mean, stat_std, stat_min, stat_max, stat_p10, stat_p90
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (user_id, tag, metric)
                DO UPDATE SET
                    plot_image_base64 = EXCLUDED.plot_image_base64,
                    plot_metadata = EXCLUDED.plot_metadata,
                    data_points_count = EXCLUDED.data_points_count,
                    date_range_start = EXCLUDED.date_range_start,
                    date_range_end = EXCLUDED.date_range_end,
                    stat_mean = EXCLUDED.stat_mean,
                    stat_std = EXCLUDED.stat_std,
                    stat_min = EXCLUDED.stat_min,
                    stat_max = EXCLUDED.stat_max,
                    stat_p10 = EXCLUDED.stat_p10,
                    stat_p90 = EXCLUDED.stat_p90,
                    updated_at = NOW()
                RETURNING plot_id
            """, (
                user_id, tag, metric, plot_image_base64, json.dumps(plot_metadata),
                data_points_count, date_range_start, date_range_end,
                stat_mean, stat_std, stat_min, stat_max, stat_p10, stat_p90
            ))
            
            result = cur.fetchone()
            plot_id = result[0] if result else None
            
            # Explicit check for silent failure
            if plot_id is None:
                logger.error(f"Database upsert returned NULL plot_id - silent failure detected")
                logger.error(f"Parameters: user_id={user_id}, tag={tag}, metric={metric}")
                logger.error(f"Data lengths: plot_data={len(plot_image_base64)}, metadata={len(json.dumps(plot_metadata))}")
                # Check if there were any database warnings or notices
                for notice in conn.notices:
                    logger.error(f"Database notice: {notice}")
            
            conn.commit()
            
            logger.info(f"Successfully upserted plot for user {user_id}, tag {tag}, metric {metric}")
            return str(plot_id)
            
        except Exception as e:
            logger.error(f"Error upserting plot: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def get_user_plots(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all plots for a user
        
        Args:
            user_id: User UUID
            
        Returns:
            List of plot dictionaries
        """
        try:
            conn = self.connection_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("SELECT * FROM get_user_hrv_plots(%s)", (user_id,))
            plots = cur.fetchall()
            
            # Convert to list of dictionaries
            result = []
            for plot in plots:
                plot_dict = dict(plot)
                # Parse JSON metadata
                if plot_dict.get('plot_metadata'):
                    plot_dict['plot_metadata'] = json.loads(plot_dict['plot_metadata']) if isinstance(plot_dict['plot_metadata'], str) else plot_dict['plot_metadata']
                result.append(plot_dict)
            
            logger.info(f"Retrieved {len(result)} plots for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting user plots: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def get_plot_by_tag_metric(self, user_id: str, tag: str, metric: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific plot by user, tag, and metric
        
        Args:
            user_id: User UUID
            tag: Session tag
            metric: HRV metric name
            
        Returns:
            Plot dictionary if found, None otherwise
        """
        try:
            conn = self.connection_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM public.hrv_plots 
                WHERE user_id = %s AND tag = %s AND metric = %s
            """, (user_id, tag, metric))
            
            plot = cur.fetchone()
            if plot:
                plot_dict = dict(plot)
                # Parse JSON metadata
                if plot_dict.get('plot_metadata'):
                    plot_dict['plot_metadata'] = json.loads(plot_dict['plot_metadata']) if isinstance(plot_dict['plot_metadata'], str) else plot_dict['plot_metadata']
                return plot_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting plot by tag/metric: {e}")
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def delete_user_plots_by_tag(self, user_id: str, tag: str) -> bool:
        """
        Delete all plots for a user with a specific tag
        (Used when sessions of that tag are deleted)
        
        Args:
            user_id: User UUID
            tag: Session tag to delete plots for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            
            cur.execute("""
                DELETE FROM public.hrv_plots 
                WHERE user_id = %s AND tag = %s
            """, (user_id, tag))
            
            deleted_count = cur.rowcount
            conn.commit()
            
            logger.info(f"Deleted {deleted_count} plots for user {user_id}, tag {tag}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting plots by tag: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def refresh_plots_for_user_tag(self, user_id: str, tag: str) -> Dict[str, bool]:
        """
        Refresh all plots for a specific user and tag
        This is called when new sessions are added or existing ones are modified
        
        Args:
            user_id: User UUID
            tag: Session tag to refresh plots for
            
        Returns:
            Dictionary with success status for each metric
        """
        # Check if required functions are available
        if generate_hrv_plot is None or get_sessions_data_for_plot is None:
            logger.error("Required functions not available due to import issues")
            return {metric: False for metric in ['mean_hr', 'mean_rr', 'count_rr', 'rmssd', 'sdnn', 'pnn50', 'cv_rr', 'defa', 'sd2_sd1']}
        
        # HRV metrics to generate plots for
        metrics = ['mean_hr', 'mean_rr', 'count_rr', 'rmssd', 'sdnn', 'pnn50', 'cv_rr', 'defa', 'sd2_sd1']
        results = {}
        
        try:
            # Get sessions data for this user and tag
            sessions_data, sleep_events_data = get_sessions_data_for_plot(user_id, tag)
            
            if not sessions_data and not sleep_events_data:
                logger.info(f"No data found for user {user_id}, tag {tag} - skipping plot generation")
                return {metric: False for metric in metrics}
            
            # Generate and store plot for each metric
            for metric in metrics:
                try:
                    logger.info(f"Starting plot generation for metric: {metric}")
                    # Generate plot
                    plot_result = generate_hrv_plot(sessions_data, sleep_events_data, metric, tag)
                    logger.info(f"Plot generation result for {metric}: success={plot_result.get('success') if plot_result else 'None'}")
                    
                    if plot_result and plot_result.get('success'):
                        # Store in database
                        # Extract date range safely
                        date_range = plot_result['metadata'].get('date_range')
                        date_range_start = None
                        date_range_end = None
                        
                        if date_range and date_range != 'N/A' and ' to ' in date_range:
                            try:
                                date_parts = date_range.split(' to ')
                                date_range_start = datetime.fromisoformat(date_parts[0])
                                date_range_end = datetime.fromisoformat(date_parts[1])
                            except (ValueError, IndexError) as e:
                                logger.warning(f"Failed to parse date range '{date_range}': {e}")
                        
                        try:
                            logger.info(f"Attempting to upsert plot for {metric}")
                            plot_id = self.upsert_plot(
                                user_id=user_id,
                                tag=tag,
                                metric=metric,
                                plot_image_base64=plot_result['plot_data'],
                                plot_metadata=plot_result['metadata'],
                                data_points_count=plot_result['metadata'].get('data_points', 0),
                                date_range_start=date_range_start,
                                date_range_end=date_range_end
                            )
                            logger.info(f"Successfully upserted plot for {metric}, plot_id: {plot_id}")
                        except Exception as upsert_error:
                            logger.error(f"Upsert failed for {metric}: {str(upsert_error)}")
                            results[metric] = False
                            continue
                        
                        results[metric] = plot_id is not None
                        logger.info(f"Successfully refreshed plot for {metric}, tag {tag}")
                    else:
                        results[metric] = False
                        logger.warning(f"Failed to generate plot for {metric}, tag {tag}")
                        
                except Exception as e:
                    logger.error(f"Error refreshing plot for {metric}, tag {tag}: {e}")
                    results[metric] = False
            
            return results
            
        except Exception as e:
            logger.error(f"Error refreshing plots for user {user_id}, tag {tag}: {e}")
            return {metric: False for metric in metrics}
    
    def get_plot_statistics_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get summary statistics about user's plots
        
        Args:
            user_id: User UUID
            
        Returns:
            Dictionary with plot statistics summary
        """
        try:
            conn = self.connection_pool.getconn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT 
                    tag,
                    COUNT(*) as plot_count,
                    MAX(updated_at) as last_updated,
                    AVG(data_points_count) as avg_data_points
                FROM public.hrv_plots 
                WHERE user_id = %s
                GROUP BY tag
                ORDER BY tag
            """, (user_id,))
            
            summary = cur.fetchall()
            return [dict(row) for row in summary]
            
        except Exception as e:
            logger.error(f"Error getting plot statistics summary: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)
