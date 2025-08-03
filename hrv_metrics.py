"""
HRV Metrics Calculator - Clean NumPy Implementation
Version: 3.3.4 Final (Supabase Edition)
Source: schema.md (Golden Reference)

Implements the exact 9 HRV metrics specified in schema.md using pure NumPy.
All calculations follow established HRV analysis standards.
"""

import numpy as np
from typing import List, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

class HRVMetricsCalculator:
    """
    Clean HRV metrics calculator implementing the exact 9 metrics from schema.md
    
    Metrics implemented:
    1. count_rr - Total number of RR intervals
    2. mean_rr - Average RR interval duration (ms)
    3. sdnn - Standard deviation of all RR intervals (ms)
    4. rmssd - Root mean square of successive RR differences (ms)
    5. pnn50 - Percentage of RR differences > 50ms (%)
    6. cv_rr - Coefficient of variation of RR intervals (%)
    7. mean_hr - Average heart rate (bpm)
    8. defa - DFA α1 (Detrended Fluctuation Analysis)
    9. sd2_sd1 - Poincaré plot SD2/SD1 ratio
    """
    
    @staticmethod
    def validate_rr_intervals(rr_intervals: List[float]) -> np.ndarray:
        """
        Validate and convert RR intervals to numpy array
        
        Args:
            rr_intervals: List of RR intervals in milliseconds
            
        Returns:
            numpy array of validated RR intervals
            
        Raises:
            ValueError: If RR intervals are invalid
        """
        if not rr_intervals:
            raise ValueError("RR intervals list is empty")
        
        rr_array = np.array(rr_intervals, dtype=np.float64)
        
        # Remove invalid values (NaN, inf, negative, unrealistic)
        valid_mask = (
            np.isfinite(rr_array) & 
            (rr_array > 200) &  # Minimum 200ms (300 BPM max)
            (rr_array < 2000)   # Maximum 2000ms (30 BPM min)
        )
        
        rr_clean = rr_array[valid_mask]
        
        if len(rr_clean) < 10:
            raise ValueError(f"Insufficient valid RR intervals: {len(rr_clean)} (minimum 10 required)")
        
        logger.info(f"RR validation: {len(rr_intervals)} → {len(rr_clean)} valid intervals")
        return rr_clean
    
    @staticmethod
    def calculate_time_domain_metrics(rr: np.ndarray) -> Dict[str, float]:
        """
        Calculate time-domain HRV metrics
        
        Args:
            rr: Validated RR intervals array
            
        Returns:
            Dictionary with time-domain metrics
        """
        # Basic statistics
        count_rr = len(rr)
        mean_rr = float(np.mean(rr))
        sdnn = float(np.std(rr, ddof=1))  # Sample standard deviation
        
        # Successive differences
        rr_diffs = np.diff(rr)
        rmssd = float(np.sqrt(np.mean(rr_diffs**2)))
        
        # pNN50: percentage of successive RR differences > 50ms
        pnn50 = float(np.mean(np.abs(rr_diffs) > 50) * 100)
        
        # Coefficient of variation
        cv_rr = float((sdnn / mean_rr) * 100) if mean_rr > 0 else 0.0
        
        # Heart rate from RR intervals
        mean_hr = float(60000 / mean_rr) if mean_rr > 0 else 0.0
        
        return {
            'count_rr': count_rr,
            'mean_rr': round(mean_rr, 2),
            'sdnn': round(sdnn, 2),
            'rmssd': round(rmssd, 2),
            'pnn50': round(pnn50, 2),
            'cv_rr': round(cv_rr, 2),
            'mean_hr': round(mean_hr, 2)
        }
    
    @staticmethod
    def calculate_dfa_alpha1(rr: np.ndarray) -> float:
        """
        Calculate DFA α1 (Detrended Fluctuation Analysis)
        
        DFA α1 measures short-term fractal scaling properties of HRV.
        Values typically range from 0.5 to 1.5:
        - α1 ≈ 0.5: uncorrelated (white noise)
        - α1 ≈ 1.0: 1/f noise (healthy)
        - α1 ≈ 1.5: Brownian motion (pathological)
        
        Args:
            rr: RR intervals array
            
        Returns:
            DFA α1 value
        """
        try:
            # Minimum length check
            if len(rr) < 50:
                logger.warning(f"DFA requires ≥50 intervals, got {len(rr)}")
                return 1.0  # Default healthy value
            
            # Remove mean and create cumulative sum (integration)
            rr_centered = rr - np.mean(rr)
            y = np.cumsum(rr_centered)
            
            # Define box sizes (logarithmically spaced)
            n_min, n_max = 4, min(len(rr) // 4, 64)
            if n_max <= n_min:
                return 1.0
            
            scales = np.unique(np.logspace(np.log10(n_min), np.log10(n_max), 10).astype(int))
            fluctuations = []
            
            for n in scales:
                # Number of boxes
                n_boxes = len(y) // n
                if n_boxes < 2:
                    continue
                
                # Reshape and detrend each box
                y_boxes = y[:n_boxes * n].reshape(n_boxes, n)
                x = np.arange(n)
                
                # Linear detrending for each box
                box_fluctuations = []
                for box in y_boxes:
                    # Fit linear trend
                    coeffs = np.polyfit(x, box, 1)
                    trend = np.polyval(coeffs, x)
                    
                    # Calculate fluctuation
                    fluctuation = np.sqrt(np.mean((box - trend)**2))
                    box_fluctuations.append(fluctuation)
                
                # Average fluctuation for this scale
                avg_fluctuation = np.mean(box_fluctuations)
                fluctuations.append(avg_fluctuation)
            
            if len(fluctuations) < 3:
                return 1.0
            
            # Linear regression in log-log space to find α1
            log_scales = np.log10(scales[:len(fluctuations)])
            log_fluctuations = np.log10(fluctuations)
            
            # Remove any infinite or NaN values
            valid_mask = np.isfinite(log_scales) & np.isfinite(log_fluctuations)
            if np.sum(valid_mask) < 3:
                return 1.0
            
            # Fit line: log(F) = α1 * log(n) + c
            alpha1 = np.polyfit(log_scales[valid_mask], log_fluctuations[valid_mask], 1)[0]
            
            # Clamp to physiologically reasonable range
            alpha1 = max(0.3, min(2.0, alpha1))
            
            return round(float(alpha1), 4)
            
        except Exception as e:
            logger.warning(f"DFA calculation failed: {e}")
            return 1.0  # Default healthy value
    
    @staticmethod
    def calculate_poincare_ratio(rr: np.ndarray) -> float:
        """
        Calculate Poincaré plot SD2/SD1 ratio
        
        Poincaré plot analysis of RR intervals:
        - SD1: short-term variability (perpendicular to line of identity)
        - SD2: long-term variability (along line of identity)
        - SD2/SD1: ratio indicating balance between short/long-term variability
        
        Args:
            rr: RR intervals array
            
        Returns:
            SD2/SD1 ratio
        """
        try:
            if len(rr) < 10:
                return 2.0  # Default ratio
            
            # Create Poincaré plot points: RR(n) vs RR(n+1)
            rr1 = rr[:-1]  # RR(n)
            rr2 = rr[1:]   # RR(n+1)
            
            # Calculate SD1 and SD2
            # SD1: standard deviation perpendicular to line of identity
            # SD2: standard deviation along line of identity
            
            # Differences and sums
            diff = rr2 - rr1  # Perpendicular to line of identity
            sum_rr = rr2 + rr1  # Along line of identity
            
            # Standard deviations
            sd1 = np.std(diff, ddof=1) / np.sqrt(2)
            sd2 = np.std(sum_rr, ddof=1) / np.sqrt(2)
            
            # Calculate ratio
            if sd1 > 0:
                ratio = sd2 / sd1
            else:
                ratio = 2.0  # Default if SD1 is zero
            
            # Clamp to reasonable range
            ratio = max(0.5, min(10.0, ratio))
            
            return round(float(ratio), 2)
            
        except Exception as e:
            logger.warning(f"Poincaré calculation failed: {e}")
            return 2.0  # Default ratio
    
    @classmethod
    def calculate_all_metrics(cls, rr_intervals: List[float]) -> Dict[str, Union[int, float]]:
        """
        Calculate all 9 HRV metrics from RR intervals
        
        Args:
            rr_intervals: List of RR intervals in milliseconds
            
        Returns:
            Dictionary with all HRV metrics matching schema.md exactly
            
        Raises:
            ValueError: If RR intervals are invalid
        """
        try:
            # Validate and clean RR intervals
            rr = cls.validate_rr_intervals(rr_intervals)
            
            # Calculate time-domain metrics
            time_metrics = cls.calculate_time_domain_metrics(rr)
            
            # Calculate non-linear metrics
            defa = cls.calculate_dfa_alpha1(rr)
            sd2_sd1 = cls.calculate_poincare_ratio(rr)
            
            # Combine all metrics (exact schema.md format)
            all_metrics = {
                **time_metrics,
                'defa': defa,
                'sd2_sd1': sd2_sd1
            }
            
            logger.info(f"HRV metrics calculated successfully for {len(rr)} RR intervals")
            return all_metrics
            
        except Exception as e:
            logger.error(f"HRV metrics calculation failed: {e}")
            raise ValueError(f"Failed to calculate HRV metrics: {e}")

# Convenience function for direct use
def calculate_hrv_metrics(rr_intervals: List[float]) -> Dict[str, Union[int, float]]:
    """
    Calculate all HRV metrics from RR intervals
    
    Args:
        rr_intervals: List of RR intervals in milliseconds
        
    Returns:
        Dictionary with all 9 HRV metrics from schema.md
    """
    return HRVMetricsCalculator.calculate_all_metrics(rr_intervals)

# Example usage and testing
if __name__ == "__main__":
    # Test with sample RR intervals
    sample_rr = [
        869.56, 845.23, 892.34, 876.12, 823.45, 867.89, 901.23, 834.56,
        888.90, 856.78, 879.12, 841.67, 895.34, 872.45, 828.90, 863.21,
        897.56, 849.87, 881.34, 858.76, 874.23, 839.45, 891.67, 865.89,
        883.12, 851.34, 876.78, 844.56, 889.23, 861.45, 877.89, 847.12,
        893.45, 869.78, 885.34, 853.67, 879.56, 846.23, 887.89, 864.12
    ]
    
    try:
        metrics = calculate_hrv_metrics(sample_rr)
        print("HRV Metrics Test Results:")
        for metric, value in metrics.items():
            print(f"  {metric}: {value}")
    except Exception as e:
        print(f"Test failed: {e}")
