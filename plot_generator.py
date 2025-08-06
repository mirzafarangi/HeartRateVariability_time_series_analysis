"""
HRV Scientific Plot Generation Module

Generates publication-quality HRV trend analysis plots using matplotlib/seaborn.
Handles all 9 HRV metrics with proper sleep/non-sleep aggregation logic.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import base64
from typing import List, Dict, Any, Optional, Tuple
import logging

# Configure matplotlib for server-side rendering
plt.switch_backend('Agg')
sns.set_style("whitegrid")
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'

logger = logging.getLogger(__name__)

class HRVPlotGenerator:
    """Generate scientific HRV trend analysis plots"""
    
    # HRV Metric configurations
    METRIC_CONFIG = {
        'mean_hr': {'unit': 'bpm', 'display_name': 'Mean Heart Rate', 'color': '#FF6B6B'},
        'mean_rr': {'unit': 'ms', 'display_name': 'Mean RR Interval', 'color': '#4ECDC4'},
        'count_rr': {'unit': 'beats', 'display_name': 'RR Count', 'color': '#45B7D1'},
        'rmssd': {'unit': 'ms', 'display_name': 'RMSSD', 'color': '#96CEB4'},
        'sdnn': {'unit': 'ms', 'display_name': 'SDNN', 'color': '#FFEAA7'},
        'pnn50': {'unit': '%', 'display_name': 'pNN50', 'color': '#DDA0DD'},
        'cv_rr': {'unit': '%', 'display_name': 'CV RR', 'color': '#98D8C8'},
        'defa': {'unit': 'ms', 'display_name': 'DFA α1', 'color': '#F7DC6F'},
        'sd2_sd1': {'unit': 'ratio', 'display_name': 'SD2/SD1', 'color': '#BB8FCE'}
    }
    
    def __init__(self, width: int = 10, height: int = 6, dpi: int = 200):
        """Initialize plot generator with mobile-friendly display parameters"""
        self.width = width
        self.height = height
        self.dpi = dpi
        
    def generate_trend_plot(self, 
                          sessions_data: List[Dict], 
                          sleep_events_data: List[Dict],
                          metric: str, 
                          tag: str,
                          title_suffix: str = "") -> Tuple[str, Dict[str, float]]:
        """
        Generate a scientific trend analysis plot for an HRV metric
        
        Args:
            sessions_data: List of session records
            sleep_events_data: List of aggregated sleep event records  
            metric: HRV metric name (e.g., 'rmssd', 'sdnn')
            tag: Selected tag filter
            title_suffix: Optional title suffix
            
        Returns:
            Tuple of (Base64 encoded PNG image string, statistics dict)
        """
        try:
            # Get metric configuration
            if metric not in self.METRIC_CONFIG:
                raise ValueError(f"Unknown metric: {metric}")
                
            config = self.METRIC_CONFIG[metric]
            
            # Prepare data based on tag type
            if tag == 'sleep':
                df = self._prepare_sleep_data(sleep_events_data, metric)
                rolling_window = 5  # 5-event rolling average for sleep
            else:
                df = self._prepare_session_data(sessions_data, metric, tag)
                rolling_window = 3  # 3-session rolling average for non-sleep
                
            if df.empty:
                empty_plot = self._generate_empty_plot(config['display_name'], tag)
                empty_stats = {'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0, 'p10': 0.0, 'p90': 0.0}
                return empty_plot, empty_stats
                
            # Create the plot with professional styling
            fig, ax = plt.subplots(figsize=(self.width, self.height), dpi=self.dpi)
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')
            
            # Calculate statistics
            values = df['value'].values
            rolling_avg = df['value'].rolling(window=rolling_window, center=True).mean()
            mean_val = float(np.mean(values))
            std_val = float(np.std(values))
            min_val = float(np.min(values))
            max_val = float(np.max(values))
            p10, p90 = np.percentile(values, [10, 90])
            p10, p90 = float(p10), float(p90)
            
            # Store calculated statistics
            calculated_stats = {
                'mean': mean_val,
                'std': std_val,
                'min': min_val,
                'max': max_val,
                'p10': p10,
                'p90': p90
            }
            
            # Professional color scheme
            primary_color = '#007AFF'  # iOS blue
            secondary_color = '#34C759'  # iOS green
            accent_color = '#FF9500'  # iOS orange
            light_gray = '#F2F2F7'  # iOS light gray
            medium_gray = '#8E8E93'  # iOS medium gray
            
            # Plot smooth SD bands with gradient effect
            ax.fill_between(df['date'], mean_val - 2*std_val, mean_val + 2*std_val, 
                           alpha=0.1, color=accent_color, label='±2 SD', linewidth=0)
            ax.fill_between(df['date'], mean_val - std_val, mean_val + std_val, 
                           alpha=0.15, color=accent_color, label='±1 SD', linewidth=0)
            
            # Plot percentile lines with subtle styling
            ax.axhline(y=p90, color=medium_gray, linestyle='--', alpha=0.6, linewidth=1.5, label='90th Percentile')
            ax.axhline(y=p10, color=medium_gray, linestyle='--', alpha=0.6, linewidth=1.5, label='10th Percentile')
            
            # Plot smooth rolling average line
            ax.plot(df['date'], rolling_avg, color=secondary_color, linewidth=3, 
                   label=f'{rolling_window}-Day Avg', zorder=3, alpha=0.9)
            
            # Plot data points with better styling
            ax.scatter(df['date'], df['value'], color=primary_color, 
                      s=60, alpha=0.8, zorder=4, label='Data Points', edgecolors='white', linewidth=1)
            
            # Formatting
            self._format_plot(ax, config, tag, title_suffix, len(df))
            
            # Add statistics text box
            stats_text = self._generate_stats_text(values, config['unit'])
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Convert to base64
            plot_base64 = self._fig_to_base64(fig)
            return plot_base64, calculated_stats
            
        except Exception as e:
            logger.error(f"Error generating plot for {metric}: {str(e)}")
            error_plot = self._generate_error_plot(str(e))
            empty_stats = {'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0, 'p10': 0.0, 'p90': 0.0}
            return error_plot, empty_stats
            
    def _prepare_session_data(self, sessions: List[Dict], metric: str, tag: str) -> pd.DataFrame:
        """Prepare session data for plotting"""
        # CRITICAL FIX: HRV metrics are NESTED under 'hrv_metrics' in API response
        filtered_sessions = [s for s in sessions 
                           if s.get('tag') == tag and 
                           s.get('hrv_metrics', {}).get(metric) is not None]
        
        if not filtered_sessions:
            logger.warning(f"No sessions found for tag={tag} with metric={metric}")
            return pd.DataFrame()
            
        logger.info(f"Found {len(filtered_sessions)} sessions for tag={tag}, metric={metric}")
            
        try:
            df = pd.DataFrame([{
                'date': datetime.fromisoformat(s['recorded_at'].replace('Z', '+00:00')),
                'value': float(s['hrv_metrics'][metric])  # CRITICAL FIX: Access nested metric fields
            } for s in filtered_sessions])
            
            return df.sort_values('date')
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error processing session data for {metric}: {str(e)}")
            return pd.DataFrame()
        
    def _prepare_sleep_data(self, sleep_events: List[Dict], metric: str) -> pd.DataFrame:
        """Prepare sleep event data for plotting"""
        # Filter events that have the metric
        metric_key = f'avg_{metric}' if not metric.startswith('avg_') else metric
        filtered_events = [e for e in sleep_events if e.get(metric_key) is not None]
        
        if not filtered_events:
            return pd.DataFrame()
            
        df = pd.DataFrame([{
            'date': datetime.fromisoformat(e['date'].replace('Z', '+00:00')),
            'value': float(e[metric_key])
        } for e in filtered_events])
        
        return df.sort_values('date')
        
    def _format_plot(self, ax, config: Dict, tag: str, title_suffix: str, df_length: int = 1):
        """Apply professional mobile-friendly formatting to the plot"""
        # Professional title with better typography
        title = f"{config['display_name']} Trend Analysis - {tag.title()}"
        if title_suffix:
            title += f" {title_suffix}"
        ax.set_title(title, fontsize=14, fontweight='600', pad=15, color='#1C1C1E')
        
        # Clean axes labels with iOS-style typography
        ax.set_xlabel('Date', fontsize=11, fontweight='500', color='#3C3C43')
        ax.set_ylabel(f"{config['display_name']} ({config['unit']})", fontsize=11, fontweight='500', color='#3C3C43')
        
        # Professional date formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        interval = max(1, df_length // 6) if df_length > 6 else 1
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, fontsize=9, color='#8E8E93')
        plt.setp(ax.yaxis.get_majorticklabels(), fontsize=9, color='#8E8E93')
        
        # Subtle grid with iOS-style colors
        ax.grid(True, alpha=0.2, color='#C7C7CC', linewidth=0.5)
        ax.set_axisbelow(True)
        
        # Professional legend with better positioning
        legend = ax.legend(loc='upper right', framealpha=0.95, fancybox=True, 
                          shadow=False, fontsize=8, edgecolor='#E5E5EA')
        legend.get_frame().set_facecolor('#FFFFFF')
        
        # Remove top and right spines for cleaner look
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#E5E5EA')
        ax.spines['bottom'].set_color('#E5E5EA')
        
        # Tight layout with proper padding
        plt.tight_layout(pad=1.5)
        
    def _generate_stats_text(self, values: np.ndarray, unit: str) -> str:
        """Generate statistics text box content"""
        return f"""Statistics:
Mean: {np.mean(values):.1f} {unit}
Std Dev: {np.std(values):.1f} {unit}
Min: {np.min(values):.1f} {unit}
Max: {np.max(values):.1f} {unit}
Count: {len(values)}"""
        
    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 string"""
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close(fig)
        return image_base64
        
    def _generate_empty_plot(self, metric_name: str, tag: str) -> str:
        """Generate empty plot for no data scenarios"""
        fig, ax = plt.subplots(figsize=(self.width, self.height), dpi=self.dpi)
        ax.text(0.5, 0.5, f'No {tag} data available for {metric_name}', 
               horizontalalignment='center', verticalalignment='center',
               transform=ax.transAxes, fontsize=16)
        ax.set_title(f"{metric_name} - {tag.title()}", fontsize=16, fontweight='bold')
        return self._fig_to_base64(fig)
        
    def _generate_error_plot(self, error_msg: str) -> str:
        """Generate error plot"""
        fig, ax = plt.subplots(figsize=(self.width, self.height), dpi=self.dpi)
        ax.text(0.5, 0.5, f'Error generating plot:\n{error_msg}', 
               horizontalalignment='center', verticalalignment='center',
               transform=ax.transAxes, fontsize=14, color='red')
        ax.set_title("Plot Generation Error", fontsize=16, fontweight='bold')
        return self._fig_to_base64(fig)

def generate_hrv_plot(sessions_data: List[Dict], 
                     sleep_events_data: List[Dict],
                     metric: str, 
                     tag: str) -> Dict[str, Any]:
    """
    Convenience function to generate HRV plot with error handling
    
    Returns:
        Dictionary with success status, plot data, and metadata
    """
    try:
        logger.info(f"Starting plot generation for metric={metric}, tag={tag}")
        logger.info(f"Sessions data count: {len(sessions_data)}, Sleep events count: {len(sleep_events_data)}")
        
        generator = HRVPlotGenerator()
        plot_base64, calculated_stats = generator.generate_trend_plot(sessions_data, sleep_events_data, metric, tag)
        
        # Create metadata with calculated statistics
        metadata = {
            'metric': metric,
            'tag': tag,
            'data_points': len(sessions_data) if tag != 'sleep' else len(sleep_events_data),
            'date_range': 'N/A',  # Will be calculated properly later
            'statistics': calculated_stats
        }
        
        logger.info(f"Plot generation successful for metric={metric}, tag={tag}")
        return {
            'success': True,
            'plot_data': plot_base64,
            'metadata': metadata
        }
        
    except Exception as e:
        logger.error(f"Plot generation failed for metric={metric}, tag={tag}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'plot_data': None,
            'metadata': None
        }
