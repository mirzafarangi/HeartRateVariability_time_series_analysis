"""
Modular Session Validator for HRV API
Clean architecture for session validation with extensible modules
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of session validation"""
    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None, 
                 details: Dict = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.details = details or {}
    
    def to_dict(self):
        """Convert to dictionary for API response"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": self.details
        }


class SessionValidator:
    """Modular session validator with clean architecture"""
    
    def __init__(self):
        self.validators = []
        self._register_default_validators()
    
    def _register_default_validators(self):
        """Register default validation modules"""
        self.validators.append(self._validate_duration_critical)
        # Future validators can be added here:
        # self.validators.append(self._validate_hrv_quality)
        # self.validators.append(self._validate_artifact_detection)
    
    def validate(self, session_data: Dict) -> ValidationResult:
        """
        Run all validation modules on session data
        
        Args:
            session_data: Dictionary containing session information
                - duration_minutes: Duration from iOS (integer)
                - rr_intervals: List of RR intervals in milliseconds
                - tag: Session tag
                - subtag: Session subtag
                
        Returns:
            ValidationResult with detailed validation information
        """
        errors = []
        warnings = []
        details = {}
        
        # Run each validator
        for validator in self.validators:
            result = validator(session_data)
            if not result.is_valid:
                errors.extend(result.errors)
            warnings.extend(result.warnings)
            details.update(result.details)
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def _validate_duration_critical(self, session_data: Dict) -> ValidationResult:
        """
        Validate duration using RR intervals (critical validation)
        
        This is the first module of validation:
        - Calculate actual duration from RR intervals (duration_critical)
        - Compare with iOS-reported duration
        - Allow ±5 seconds tolerance
        """
        errors = []
        warnings = []
        details = {}
        
        try:
            # Get iOS-reported duration in minutes
            duration_ios_minutes = session_data.get('duration_minutes', 0)
            duration_ios_seconds = duration_ios_minutes * 60
            
            # Get RR intervals
            rr_intervals = session_data.get('rr_intervals', [])
            
            # Basic validation
            if not rr_intervals:
                errors.append("No RR intervals provided")
                details['duration_critical_seconds'] = 0
                details['duration_ios_seconds'] = duration_ios_seconds
                return ValidationResult(is_valid=False, errors=errors, details=details)
            
            if duration_ios_minutes < 1:
                errors.append(f"Duration too short: {duration_ios_minutes} minutes (minimum 1 minute required)")
                details['duration_ios_minutes'] = duration_ios_minutes
                return ValidationResult(is_valid=False, errors=errors, details=details)
            
            # Calculate critical duration from RR intervals
            # Sum of all RR intervals gives actual recording duration
            duration_critical_ms = sum(rr_intervals)
            duration_critical_seconds = duration_critical_ms / 1000.0
            duration_critical_minutes = duration_critical_seconds / 60.0
            
            # Calculate difference
            duration_diff_seconds = abs(duration_ios_seconds - duration_critical_seconds)
            
            # Store details for reporting
            details['duration_ios_minutes'] = duration_ios_minutes
            details['duration_ios_seconds'] = duration_ios_seconds
            details['duration_critical_seconds'] = round(duration_critical_seconds, 2)
            details['duration_critical_minutes'] = round(duration_critical_minutes, 2)
            details['duration_difference_seconds'] = round(duration_diff_seconds, 2)
            details['rr_interval_count'] = len(rr_intervals)
            
            # Check tolerance (±5 seconds)
            TOLERANCE_SECONDS = 5
            if duration_diff_seconds > TOLERANCE_SECONDS:
                error_msg = (
                    f"Duration mismatch: iOS reported {duration_ios_minutes} min "
                    f"({duration_ios_seconds}s), but RR intervals show "
                    f"{round(duration_critical_minutes, 1)} min ({round(duration_critical_seconds, 1)}s). "
                    f"Difference: {round(duration_diff_seconds, 1)}s (tolerance: ±{TOLERANCE_SECONDS}s)"
                )
                errors.append(error_msg)
                
                # Log for debugging
                logger.warning(f"Duration validation failed: {error_msg}")
                logger.debug(f"RR intervals: count={len(rr_intervals)}, "
                           f"first_10={rr_intervals[:10] if len(rr_intervals) > 10 else rr_intervals}")
            else:
                # Duration is within tolerance
                details['validation_status'] = 'PASSED'
                logger.info(f"Duration validation passed: iOS={duration_ios_minutes}min, "
                          f"Critical={round(duration_critical_minutes, 2)}min, "
                          f"Diff={round(duration_diff_seconds, 2)}s")
            
            # Add warnings for edge cases
            if len(rr_intervals) < 10:
                warnings.append(f"Low RR interval count ({len(rr_intervals)}). HRV metrics may be unreliable.")
            
            if duration_critical_minutes < 1:
                warnings.append(f"Actual recording duration is {round(duration_critical_minutes, 2)} minutes")
            
        except Exception as e:
            logger.error(f"Error in duration validation: {str(e)}")
            errors.append(f"Duration validation error: {str(e)}")
        
        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )
    
    def get_validation_report(self, session_data: Dict) -> Dict:
        """
        Generate a comprehensive validation report for UI display
        
        Returns a structured report suitable for iOS queue card display
        """
        result = self.validate(session_data)
        
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_data.get('session_id', 'unknown'),
            "validation_result": result.to_dict(),
            "session_summary": {
                "tag": session_data.get('tag', 'unknown'),
                "subtag": session_data.get('subtag', 'unknown'),
                "event_id": session_data.get('event_id', 0),
                "duration_minutes": session_data.get('duration_minutes', 0),
                "rr_interval_count": len(session_data.get('rr_intervals', []))
            }
        }
        
        return report


# Singleton instance
session_validator = SessionValidator()
