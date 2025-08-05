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
    
    def __init__(self, width: int = 12, height: int = 8, dpi: int = 150):
        """Initialize plot generator with display parameters"""
        self.width = width
        self.height = height
        self.dpi = dpi
        
    def generate_trend_plot(self, 
                          sessions_data: List[Dict], 
                          sleep_events_data: List[Dict],
                          metric: str, 
                          tag: str,
                          title_suffix: str = "") -> str:
        """
        Generate a scientific trend analysis plot for an HRV metric
        
        Args:
            sessions_data: List of session records
            sleep_events_data: List of aggregated sleep event records  
            metric: HRV metric name (e.g., 'rmssd', 'sdnn')
            tag: Selected tag filter
            title_suffix: Optional title suffix
            
        Returns:
            Base64 encoded PNG image string
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
                return self._generate_empty_plot(config['display_name'], tag)
                
            # Create the plot
            fig, ax = plt.subplots(figsize=(self.width, self.height), dpi=self.dpi)
            
            # Calculate statistics
            values = df['value'].values
            rolling_avg = df['value'].rolling(window=rolling_window, center=True).mean()
            mean_val = np.mean(values)
            std_val = np.std(values)
            p10, p90 = np.percentile(values, [10, 90])
            
            # Plot SD bands (±1 and ±2 standard deviations)
            ax.fill_between(df['date'], mean_val - 2*std_val, mean_val + 2*std_val, 
                           alpha=0.15, color='red', label='±2 SD')
            ax.fill_between(df['date'], mean_val - std_val, mean_val + std_val, 
                           alpha=0.25, color='orange', label='±1 SD')
            
            # Plot percentile lines
            ax.axhline(y=p90, color='gray', linestyle='--', alpha=0.7, linewidth=2, label='90th Percentile')
            ax.axhline(y=p10, color='gray', linestyle='--', alpha=0.7, linewidth=2, label='10th Percentile')
            
            # Plot rolling average line
            ax.plot(df['date'], rolling_avg, color='green', linewidth=3, 
                   label=f'{rolling_window}-Point Average', zorder=3)
            
            # Plot data points
            ax.scatter(df['date'], df['value'], color=config['color'], 
                      s=80, alpha=0.8, zorder=4, label='Data Points')
            
            # Formatting
            self._format_plot(ax, config, tag, title_suffix)
            
            # Add statistics text box
            stats_text = self._generate_stats_text(values, config['unit'])
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # Convert to base64
            return self._fig_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Error generating plot for {metric}: {str(e)}")
            return self._generate_error_plot(str(e))
            
    def _prepare_session_data(self, sessions: List[Dict], metric: str, tag: str) -> pd.DataFrame:
        """Prepare session data for plotting"""
        filtered_sessions = [s for s in sessions if s.get('tag') == tag and s.get(metric) is not None]
        
        if not filtered_sessions:
            return pd.DataFrame()
            
        df = pd.DataFrame([{
            'date': datetime.fromisoformat(s['recorded_at'].replace('Z', '+00:00')),
            'value': float(s[metric])
        } for s in filtered_sessions])
        
        return df.sort_values('date')
        
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
        
    def _format_plot(self, ax, config: Dict, tag: str, title_suffix: str):
        """Apply scientific formatting to the plot"""
        # Title
        title = f"{config['display_name']} Trend Analysis - {tag.title()}"
        if title_suffix:
            title += f" {title_suffix}"
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        
        # Axes labels
        ax.set_xlabel('Date', fontsize=12, fontweight='semibold')
        ax.set_ylabel(f"{config['display_name']} ({config['unit']})", fontsize=12, fontweight='semibold')
        
        # Date formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(ax.get_xticklabels()) // 6)))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Grid and styling
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', framealpha=0.9)
        
        # Tight layout
        plt.tight_layout()
        
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
        plot_base64 = generator.generate_trend_plot(sessions_data, sleep_events_data, metric, tag)
        
        # Create metadata
        metadata = {
            'metric': metric,
            'tag': tag,
            'data_points': len(sessions_data) if tag != 'sleep' else len(sleep_events_data),
            'date_range': 'N/A',  # Will be calculated properly later
            'statistics': {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'p10': 0.0,
                'p90': 0.0
            }
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
